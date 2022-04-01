import time
from audioop import add
from email.headerregistry import Address
import os
from algosdk import *
from algosdk.v2client import algod, indexer
from algosdk.v2client.models import DryrunSource, DryrunRequest
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from algosdk.encoding import checksum, encode_address
from algosdk import util

from sandbox import get_accounts

from src.contracts.climatecoin_vault_asc import get_approval, get_clear
from src.utils import print_asset_holding, get_dummy_metadata, get_asset_holding
from utils import compile_program, wait_for_confirmation

import json
import hashlib
import base64

token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
url = "http://localhost:4001"
# url = "https://node.testnet.algoexplorerapi.io"
indexer_url = "http://localhost:8980"
# indexer_url = "https://algoindexer.testnet.algoexplorerapi.io"
deployer_mnemonic = "light tent note stool aware mother nice impulse chair tobacco rib mountain roof key crystal author sail rural divide labor session sleep neutral absorb useful"
random_user = "know tag story install insect good diagram crumble drop impact brush trash review endless border timber reflect machine ship pig sample ugly salad about act"
random_user_ONLY_ONCE = "laptop pink throw human job expect talent december erase base entry wear exile degree hole argue float under giraffe bid fold only shine above tooth"

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
    # manager_pk = mnemonic.to_private_key(deployer_mnemonic)
    # manager_addr = account.address_from_private_key(manager_pk)
    manager_addr, manager_pk = get_accounts()[0]

    manager_signer = AccountTransactionSigner(manager_pk)
    print("Using {}".format(manager_addr))

    # Create random user acct
    # user_pk = mnemonic.to_private_key(random_user)
    # user_addr = account.address_from_private_key(user_pk)
    user_addr, user_pk = get_accounts()[1]

    user_signer = AccountTransactionSigner(user_pk)
    print("Using {}".format(user_addr))

    # Create app
    app_id = create_app(manager_addr, manager_pk)
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
                txn=PaymentTxn(manager_addr, sp, get_escrow_from_app(app_id), util.algos_to_microalgos(1), None),
                signer=manager_signer
            )
        )

        sp.fee = sp.min_fee * 3

        atc.add_method_call(app_id, get_method(iface, "mint_climatecoin"), manager_addr, sp, manager_signer, [])
        atc.add_method_call(app_id, get_method(iface, "set_minter_address"), manager_addr, sp, manager_signer,
                            [manager_addr])
        # atc.add_method_call(app_id, get_method(iface, "set_oracle_address"), addr, sp, addr_signer, [oracle_addr])

        result = atc.execute(client, 4)
        for res in result.abi_results:
            print(res.return_value)
        climatecoin_asa_id = result.abi_results[0].return_value

        #
        # Optin to climatecoin
        print("[ 0 ] user opted into climatecoin")
        atc = AtomicTransactionComposer()
        atc.add_transaction(
            TransactionWithSigner(
                txn=AssetTransferTxn(user_addr, sp, user_addr, 0, climatecoin_asa_id), signer=user_signer
            )
        )
        atc.execute(client, 2)

        #
        # Mint  some nfts
        sp = client.suggested_params()
        atc = AtomicTransactionComposer()
        # Dummy metadata
        metadata_json, encoded = get_dummy_metadata()
        nft_total_supply = 250

        atc.add_method_call(app_id, get_method(iface, "create_nft"), manager_addr, sp, manager_signer,
                            [nft_total_supply], note=metadata_json.encode())
        results = atc.execute(client, 2)

        created_nft_id = results.abi_results[0].return_value
        print("Created nft {}".format(created_nft_id))

        print("[ 1 ] User optin to NFT")
        sp = client.suggested_params()
        atc = AtomicTransactionComposer()

        # Optin to the created NFT
        atc.add_transaction(
            TransactionWithSigner(
                txn=AssetTransferTxn(user_addr, sp, user_addr, 0, created_nft_id), signer=user_signer
            )
        )
        print("[ 1 ] Manager calling move method")
        tokens_to_move = get_asset_holding(indexer_client, get_escrow_from_app(app_id), created_nft_id)
        atc.add_method_call(
            app_id,
            get_method(iface, "move"),
            manager_addr,
            sp,
            manager_signer,
            [created_nft_id, get_escrow_from_app(app_id), user_addr, tokens_to_move],
        )
        atc.execute(client, 2)
        print_asset_holding(indexer_client, user_addr, created_nft_id)

        #
        # Swap them
        atc = AtomicTransactionComposer()
        print("[ 1 ] User swaps the asset")
        # add random nonce in note so we can send identicall txns
        atc.add_method_call(app_id, get_method(iface, "unfreeze_nft"), user_addr, sp, user_signer,
                            [created_nft_id], note=os.urandom(1))
        atc.add_method_call(app_id, get_method(iface, "swap_nft_to_fungible"), user_addr, sp, user_signer,
                            [created_nft_id], foreign_assets=[climatecoin_asa_id], note=os.urandom(1))
        atc.execute(client, 4)
        print_asset_holding(indexer_client, user_addr, climatecoin_asa_id)


        #
        # Do it again
        print("[ X ] doing it again...")
        # Mint  some nfts
        sp = client.suggested_params()
        atc = AtomicTransactionComposer()
        # Dummy metadata
        metadata_json, encoded = get_dummy_metadata()
        nft_total_supply = 2000

        atc.add_method_call(app_id, get_method(iface, "create_nft"), manager_addr, sp, manager_signer,
                            [nft_total_supply], note=metadata_json.encode())
        results = atc.execute(client, 2)

        created_nft_id = results.abi_results[0].return_value
        print("[ 2 ] Created nft {}".format(created_nft_id))

        print("[ 2 ] User opt-in to NFT")
        sp = client.suggested_params()
        atc = AtomicTransactionComposer()
        # Optin to the created NFT
        atc.add_transaction(
            TransactionWithSigner(
                txn=AssetTransferTxn(user_addr, sp, user_addr, 0, created_nft_id), signer=user_signer
            )
        )
        print("[ 2 ] Manager calling move method")
        tokens_to_move = get_asset_holding(indexer_client, get_escrow_from_app(app_id), created_nft_id)
        atc.add_method_call(
            app_id,
            get_method(iface, "move"),
            manager_addr,
            sp,
            manager_signer,
            [created_nft_id, get_escrow_from_app(app_id), user_addr, tokens_to_move],
        )
        atc.execute(client, 4)
        print_asset_holding(indexer_client, user_addr, created_nft_id)

        print("[ 2 ] User calling swap method")
        atc = AtomicTransactionComposer()
        # add random nonce in note so we can send identical txns
        atc.add_method_call(app_id, get_method(iface, "swap_nft_to_fungible"), user_addr, sp, user_signer,
                            [created_nft_id], foreign_assets=[climatecoin_asa_id], note=os.urandom(1))
        atc.execute(client, 4)
        # give the indexer time to update
        time.sleep(1)
        print_asset_holding(indexer_client, user_addr, climatecoin_asa_id)
    except Exception as e:
        print(e)
    finally:
        #
        # Delete app
        atc = AtomicTransactionComposer()
        atc.add_transaction(
            TransactionWithSigner(
                txn=ApplicationDeleteTxn(manager_addr, sp, app_id), signer=manager_signer
            )
        )
        atc.execute(client, 4)
        print(f"{app_id} was succesfully deleted")



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
