from algosdk import *
from algosdk.v2client import algod, indexer
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from algosdk.encoding import checksum, encode_address
from algosdk import util

from src.contracts.climatecoin_vault_asc import get_approval, get_clear
from src.utils import compile_program, wait_for_confirmation

token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
url = "https://node.testnet.algoexplorerapi.io"
indexer_url = "https://algoindexer.testnet.algoexplorerapi.io"
deployer_mnemonic="light tent note stool aware mother nice impulse chair tobacco rib mountain roof key crystal author sail rural divide labor session sleep neutral absorb useful"

client = algod.AlgodClient(token, url)
indexer_client = indexer.IndexerClient(
    token, indexer_url
)
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
    pk = mnemonic.to_private_key(deployer_mnemonic)
    addr = account.address_from_private_key(pk)
    # addr, pk = get_accounts()[0]
    addr_signer = AccountTransactionSigner(pk)
    print("Using {}".format(addr))

    # Create app
    app_id = create_app(addr, pk)
    print("Created App with id: {}".format(app_id))

    app_addr = logic.get_application_address(app_id)
    print("Application Address: {}".format(app_addr))

    try:
        sp = client.suggested_params()
        #
        # Setup the smart contract
        atc = AtomicTransactionComposer()

        #
        # TODO: how many algos does this cost? do we have to up the fee?
        # cover for the 2 innerTxns
        sp.fee = sp.min_fee * 3
        atc.add_transaction(
            TransactionWithSigner(
                txn=PaymentTxn(addr, sp, get_escrow_from_app(app_id), util.algos_to_microalgos(1), None), signer=addr_signer
            )
        )

        sp.fee = sp.min_fee * 3

        atc.add_method_call(app_id, get_method(iface, "mint_climatecoin"), addr, sp, addr_signer, [])
        atc.add_method_call(app_id, get_method(iface, "set_minter_address"), addr, sp, addr_signer, [addr])
        
        result = atc.execute(client, 4)
        for res in result.abi_results:
            print(res.return_value)
        climatecoin_asa_id = result.abi_results[0].return_value


    except Exception as e:
        print(e)


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
    approval_program = compile_program(client, get_approval())
    
    # Read in clear teal source && compile 
    clear_program = compile_program(client, get_clear())

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


if __name__ == "__main__":
    demo()