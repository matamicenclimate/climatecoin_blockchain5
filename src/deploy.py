from audioop import add
from email.headerregistry import Address
from algosdk import *
from algosdk.v2client import algod
from algosdk.v2client.models import DryrunSource, DryrunRequest
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from algosdk.encoding import checksum, encode_address
from algosdk import util

from sandbox import get_accounts

from contracts.climatecoin_vault_asc import mint_climatecoin_selector, contract, contract_clear
from utils import compile_program, wait_for_confirmation

token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
url = "http://localhost:4001"
# url = "https://node.testnet.algoexplorerapi.io"
deployer_mnemonic = "reward remove stairs topic disorder town prison town angry gas tray home obvious biology distance belt champion human rotate coin antique gospel grit ability game"

client = algod.AlgodClient(token, url)

# Read in ABI description
with open("src/contracts/climatecoin_vault_asc.json") as f:
    iface = Interface.from_json(f.read())


def get_method(i: Interface, name: str) -> Method:
    for m in i.methods:
        if m.name == name:
            return m
    raise Exception("No method with the name {}".format(name))

def get_escrow_from_app(app_id):
    return encode_address(checksum(b"appID" + (app_id).to_bytes(8, "big")))


def demo():
    # Create acct
    # pk = mnemonic.to_private_key(deployer_mnemonic)
    # addr = account.address_from_private_key(pk)
    addr, pk = get_accounts()[0]
    print("Using {}".format(addr))

    # this will be our backend oracle, but we mock it for now
    oracle_addr, oracle_pk = get_accounts()[1]
    print("Using oracle {}".format(oracle_addr))
    
    # Create app
    app_id = create_app(addr, pk)
    print("Created App with id: {}".format(app_id))

    app_addr = logic.get_application_address(app_id)
    print("Application Address: {}".format(app_addr))

    #
    # Setup the smart contract
    atc = AtomicTransactionComposer()
    signer = AccountTransactionSigner(pk)
    sp = client.suggested_params()
    print(mint_climatecoin_selector.methodName)
    
    atc.add_transaction(
        TransactionWithSigner(
            txn=PaymentTxn(addr, sp, get_escrow_from_app(app_id), util.algos_to_microalgos(1), None), signer=signer
        )
    )

    sp.fee = sp.min_fee * 3

    atc.add_method_call(app_id, get_method(iface, "mint_climatecoin"), addr, sp, signer)
    atc.add_method_call(app_id, get_method(iface, "set_minter_address"), addr, sp, signer, [addr])
    atc.add_method_call(app_id, get_method(iface, "set_oracle_address"), addr, sp, signer, [oracle_addr])
    
    result = atc.execute(client, 4)
    for res in result.abi_results:
        print(res.return_value)

    #
    # Mint  some nfts

    nft_id = create_asset(addr, pk)
    print("Created CO2 nft {}".format(nft_id))

    #
    # Swap them
    atc = AtomicTransactionComposer()
    oracle = AccountTransactionSigner(oracle_pk)
    nft_value = 100 # this comes from some metadata in the arc-69
    atc.add_transaction(
        TransactionWithSigner(
            txn=AssetTransferTxn(addr, sp, get_escrow_from_app(app_id), 1, nft_id, get_escrow_from_app(app_id)), signer=signer
        )
    )
    # esto lo manda el backend al frontend
    atc.add_method_call(app_id, get_method(iface, "set_swap_price"), oracle_addr, sp, oracle, [nft_value])
    atc.add_method_call(app_id, get_method(iface, "swap_nft_to_fungible"), addr, sp, signer, [nft_id, nft_value])
    
    group = atc.submit(client)
    print(group)
    result = wait_for_confirmation(client, group)



def get_app_call(addr, sp, app_id, args):
    return ApplicationCallTxn(
        addr, sp, app_id, 
        OnComplete.NoOpOC,
        app_args=args,
    )


def create_app(addr, pk):
    # Get suggested params from network 
    sp = client.suggested_params()

    # Read in approval teal source && compile
    approval_program = compile_program(client, contract())
    
    # Read in clear teal source && compile 
    clear_program = compile_program(client, contract_clear())

    global_schema = StateSchema(2, 2)
    local_schema = StateSchema(0, 0)

    # Create the transaction
    create_txn = ApplicationCreateTxn(addr, sp, 0, approval_program, clear_program, global_schema, local_schema)

    # Sign it
    signed_txn = create_txn.sign(pk)

    # Ship it
    txid = client.send_transaction(signed_txn)
    
    # Wait for the result so we can return the app id
    result = wait_for_confirmation(client, txid)

    return result['application-index']


def create_asset(addr, pk):
    # Get suggested params from network 
    sp = client.suggested_params()

    # Create the transaction
    asset_config_txn = AssetConfigTxn(
        addr,
        sp,
        total=1,
        manager=addr,
        reserve=addr,
        freeze=addr,
        clawback=addr,
        unit_name="CO2",
        asset_name="CO2NFT@arc-69", 
        url="daiwal.com",
        default_frozen=0
    )
    
    # Sign it
    signed_txn = asset_config_txn.sign(pk)

    # Ship it
    txid = client.send_transaction(signed_txn)
    
    # Wait for the result so we can return the app id
    result = wait_for_confirmation(client, txid)

    return result["asset-index"]


if __name__ == "__main__":
    demo()