from audioop import add
from email.headerregistry import Address
import os
from algosdk import *
from algosdk.v2client import algod
from algosdk.v2client.models import DryrunSource, DryrunRequest
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from algosdk.encoding import checksum, encode_address
from algosdk import util

from sandbox import get_accounts

from src.contracts.climatecoin_vault_asc import get_approval, get_clear
from src.utils import print_asset_holding
from utils import compile_program, wait_for_confirmation

import json
import hashlib
import base64

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
    addr_signer = AccountTransactionSigner(pk)
    print("Using {}".format(addr))

    # this will be our backend oracle, but we mock it for now
    # oracle_addr, oracle_pk = get_accounts()[1]
    # print("Using oracle {}".format(oracle_addr))
    
    # Create app
    app_id = create_app(addr, pk)
    print("Created App with id: {}".format(app_id))

    app_addr = logic.get_application_address(app_id)
    print("Application Address: {}".format(app_addr))

    sp = client.suggested_params()
    #
    # Setup the smart contract
    atc = AtomicTransactionComposer()
    
    atc.add_transaction(
        TransactionWithSigner(
            txn=PaymentTxn(addr, sp, get_escrow_from_app(app_id), util.algos_to_microalgos(1), None), signer=addr_signer
        )
    )

    sp.fee = sp.min_fee * 3

    atc.add_method_call(app_id, get_method(iface, "mint_climatecoin"), addr, sp, addr_signer, [])
    atc.add_method_call(app_id, get_method(iface, "set_minter_address"), addr, sp, addr_signer, [addr])
    # atc.add_method_call(app_id, get_method(iface, "set_oracle_address"), addr, sp, addr_signer, [oracle_addr])
    
    result = atc.execute(client, 4)
    for res in result.abi_results:
        print(res.return_value)
    climatecoin_asa_id = result.abi_results[0].return_value

    #
    # Optin to climatecoin
    print("manager opted into climatecoin")
    atc = AtomicTransactionComposer()
    atc.add_transaction(
        TransactionWithSigner(
            txn=AssetTransferTxn(addr, sp, addr, 0, climatecoin_asa_id), signer=addr_signer
        )
    )
    atc.execute(client, 2)

    #
    # Mint  some nfts
    sp = client.suggested_params()
    atc = AtomicTransactionComposer()
    # Dummy metadata
    metadata = {
        "type": "from_date",
        "from": "1/1/2022"
    }
    metadata_json = json.dumps(metadata)
    metadata_hash = hashlib.sha256(metadata_json.encode()).digest()[:32]
    hash_as_str=base64.b64encode(metadata_hash).decode('utf-8')

    nft_total_supply = 1000

    atc.add_method_call(app_id, get_method(iface, "create_nft"), addr, sp, addr_signer, [hash_as_str, metadata_json, nft_total_supply])
    results = atc.execute(client, 2)

    created_nft_id = results.abi_results[0].return_value
    print("Created nft {}".format(created_nft_id))

    print("Optin to method")
    sp = client.suggested_params()
    atc = AtomicTransactionComposer()
    # Optin to the created NFT
    atc.add_transaction(
        TransactionWithSigner(
            txn=AssetTransferTxn(addr, sp, addr, 0, created_nft_id), signer=addr_signer
        )
    )
    print("Calling move method")
    atc.add_method_call(
        app_id,
        get_method(iface, "move"),
        addr,
        sp,
        addr_signer,
        [created_nft_id, get_escrow_from_app(app_id), addr, 500],
    )
    atc.execute(client, 2)
    print_asset_holding(client, addr, created_nft_id)

    #
    # Swap them
    atc = AtomicTransactionComposer()
    print("Swap the asset")
    # add random nonce in note so we can send identicall txns
    atc.add_method_call(app_id, get_method(iface, "swap_nft_to_fungible"), addr, sp, addr_signer, [created_nft_id], foreign_assets=[climatecoin_asa_id], note=os.urandom(1))
    atc.execute(client, 4)
    print_asset_holding(client, addr, climatecoin_asa_id)


    #
    # Do it again
    print("calling move method")
    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id,
        get_method(iface, "move"),
        addr,
        sp,
        addr_signer,
        [created_nft_id, get_escrow_from_app(app_id), addr, 400],
    )
    atc.execute(client, 4)
    print_asset_holding(client, addr, created_nft_id)

    print("calling swap method")
    atc = AtomicTransactionComposer()
    # add random nonce in note so we can send identicall txns
    atc.add_method_call(app_id, get_method(iface, "swap_nft_to_fungible"), addr, sp, addr_signer, [created_nft_id], foreign_assets=[climatecoin_asa_id], note=os.urandom(1))
    atc.execute(client, 4)

    print_asset_holding(client, addr, climatecoin_asa_id)

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