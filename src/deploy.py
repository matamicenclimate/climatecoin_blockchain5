from email.mime import application
import os
from algosdk.v2client import indexer
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from algosdk.encoding import checksum, encode_address
from algosdk import util, mnemonic

from sandbox import get_accounts
from src.contracts.climatecoin_dump_asc import get_dump_approval, get_dump_clear

from src.contracts.climatecoin_vault_asc import get_approval, get_clear
from src.utils import get_asset_supply, print_asset_holding, get_dummy_metadata, get_asset_holding
from utils import compile_program, wait_for_confirmation

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

with open("src/contracts/climatecoin_dump_asc.json") as f:
    dump_iface = Interface.from_json(f.read())

def get_method(i: Interface, name: str) -> Method:
    for m in i.methods:
        if m.name == name:
            return m
    raise Exception("No method with the name {}".format(name))


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

    #
    # Create app
    vault_app_id = create_app(manager_addr, manager_pk)
    print("Created App with id: {}".format(vault_app_id))

    vault_app_addr = logic.get_application_address(vault_app_id)
    print("Application Address: {}".format(vault_app_addr))

    dump_app_id = create_dump_app(manager_addr, manager_pk)
    print("Created App with id: {}".format(dump_app_id))

    dump_app_addr = logic.get_application_address(dump_app_id)
    print("Dump Application Address: {}".format(dump_app_addr))

    try:
        #
        # Setup the smart contract
        sp = client.suggested_params()
        sp.fee = sp.min_fee * 3
        atc = AtomicTransactionComposer()
        #
        # TODO: how many algos does this cost? do we have to up the fee?
        # cover for the 2 innerTxns
        atc.add_transaction(
            TransactionWithSigner(
                txn=PaymentTxn(manager_addr, sp, vault_app_addr, util.algos_to_microalgos(1), None),
                signer=manager_signer
            )
        )
        atc.add_transaction(
            TransactionWithSigner(
                txn=PaymentTxn(manager_addr, sp, dump_app_addr, util.algos_to_microalgos(1), None),
                signer=manager_signer
            )
        )

        atc.add_method_call(vault_app_id, get_method(iface, "mint_climatecoin"), manager_addr, sp, manager_signer, [])
        # atc.add_method_call(vault_app_id, get_method(iface, "set_minter_address"), manager_addr, sp, manager_signer,
        #                     [manager_addr])
        atc.add_method_call(vault_app_id, get_method(iface, "set_dump"), manager_addr, sp, manager_signer,
                            [dump_app_id])
        atc.add_method_call(dump_app_id, get_method(dump_iface, "set_vault_app"), manager_addr, sp, manager_signer,
                            [vault_app_id])

        result = atc.execute(client, 4)
        for res in result.abi_results:
            print(res.return_value)
        climatecoin_asa_id = result.abi_results[0].return_value

        #
        # Optin to climatecoin
        print("[ 0 ] user optin into climatecoin")
        atc = AtomicTransactionComposer()
        atc.add_transaction(
            TransactionWithSigner(
                txn=AssetTransferTxn(user_addr, sp, user_addr, 0, climatecoin_asa_id), signer=user_signer
            )
        )
        atc.execute(client, 2)

        minted_nfts = []
        for iter in [0, 1]:
            sp = client.suggested_params()
            #
            # Mint  some nfts
            print(f"[ {iter} ] mint an NFT", )
            atc = AtomicTransactionComposer()
            sp.fee = sp.min_fee * 3
            # Dummy metadata
            metadata_json, encoded = get_dummy_metadata()
            nft_total_supply = 250

            atc.add_method_call(vault_app_id, get_method(iface, "create_nft"), manager_addr, sp, manager_signer,
                                [nft_total_supply, dump_app_id, dump_app_addr], note=metadata_json.encode(), )
            results = atc.execute(client, 2)

            created_nft_id = results.abi_results[0].return_value
            print("Created nft {}".format(created_nft_id))
            minted_nfts.append(created_nft_id)
            #
            # User opts-in to the NFT
            print(f"[ {iter} ] User optin to NFT")
            sp = client.suggested_params()
            atc = AtomicTransactionComposer()
            # Optin to the created NFT
            atc.add_transaction(
                TransactionWithSigner(
                    txn=AssetTransferTxn(user_addr, sp, user_addr, 0, created_nft_id), signer=user_signer
                )
            )
            result = atc.execute(client, 4)
            for res in result.abi_results:
                print(res.return_value)

            #
            # Move the NFT to the users waller
            print(f"[ {iter} ] Manager calling move method")
            tokens_to_move = get_asset_supply(indexer_client, created_nft_id)
            print(tokens_to_move)
            atc = AtomicTransactionComposer()
            atc.add_method_call(
                vault_app_id,
                get_method(iface, "move"),
                manager_addr,
                sp,
                manager_signer,
                [created_nft_id, vault_app_addr, user_addr, tokens_to_move],
            )
            result = atc.execute(client, 4)
            for res in result.abi_results:
                print(res.return_value)
            print_asset_holding(indexer_client, user_addr, created_nft_id, "user - nft")

            #
            # Print the initial asset holdings
            print(f"[ {iter} ] Initial holdings")
            print_asset_holding(indexer_client, user_addr, created_nft_id, "user - nft")
            print_asset_holding(indexer_client, user_addr, climatecoin_asa_id, "user - climatecoin")

            #
            # Swap them
            print(f"[ {iter} ] User swaps the asset")
            atc = AtomicTransactionComposer()
            # add random nonce in note so we can send identicall txns
            atc.add_method_call(vault_app_id, get_method(iface, "unfreeze_nft"), user_addr, sp, user_signer,
                                [created_nft_id], note=os.urandom(1))
            atc.add_transaction(
                TransactionWithSigner(
                    txn=AssetTransferTxn(user_addr, sp, vault_app_addr, tokens_to_move, created_nft_id), signer=user_signer
                )
            )
            atc.add_method_call(vault_app_id, get_method(iface, "swap_nft_to_fungible"), user_addr, sp, user_signer,
                                [created_nft_id], foreign_assets=[climatecoin_asa_id], note=os.urandom(1))
            atc.build_group()
            atc.execute(client, 4)

        #
        # Print the final asset holdings
        print("[ 3 ] Final holdings")
        for nft_id in minted_nfts:
            print_asset_holding(indexer_client, user_addr, nft_id, "user - nft")
        print_asset_holding(indexer_client, user_addr, climatecoin_asa_id, "user - climatecoin")

        climatecoins_to_burn = get_asset_holding(indexer_client, user_addr, climatecoin_asa_id)

        print("[ 3 ] Burn the climatecoins")
        atc = AtomicTransactionComposer()
        # add random nonce in note so we can send identicall txns
        atc.add_transaction(
            TransactionWithSigner(
                txn=AssetTransferTxn(user_addr, sp, vault_app_addr, climatecoins_to_burn - 100, climatecoin_asa_id), signer=user_signer
            )
        )
        atc.add_method_call(vault_app_id, get_method(iface, "burn_climatecoins"), user_addr, sp, user_signer,
                            accounts=[dump_app_addr], note=os.urandom(1), foreign_assets=minted_nfts)
        atc.build_group()
        result = atc.execute(client, 4)
        for res in result.abi_results:
            print(res.return_value)

        print("[ 3 ] Final balances")
        print(minted_nfts)
        print_asset_holding(indexer_client, user_addr, climatecoin_asa_id, "user - climatecoin")
        print_asset_holding(indexer_client, vault_app_addr, climatecoin_asa_id, "app - climatecoin")

        for i in range(len(minted_nfts)):
            nft_id = minted_nfts[i]
            print_asset_holding(indexer_client, user_addr, nft_id, f'user - nft {i}')
            print_asset_holding(indexer_client, vault_app_addr, nft_id, f"app - nft {i}")
            print_asset_holding(indexer_client, dump_app_addr, nft_id, f"dump - nft {i}")

    except Exception as e:
        print(e)
        
    finally:
        #
        # Delete app so we dont reach the limit of apps per account whilst testing
        atc = AtomicTransactionComposer()
        atc.add_transaction(
            TransactionWithSigner(
                txn=ApplicationDeleteTxn(manager_addr, sp, vault_app_id), signer=manager_signer
            )
        )
        atc.add_transaction(
            TransactionWithSigner(
                txn=ApplicationDeleteTxn(manager_addr, sp, dump_app_id), signer=manager_signer
            )
        )
        atc.execute(client, 4)
        print(f"{vault_app_id} was succesfully deleted")
        print(f"{dump_app_id} was succesfully deleted")



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

    global_schema = StateSchema(4, 4)
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


def create_dump_app(addr, pk):
    # Get suggested params from network 
    sp = client.suggested_params()

    # Read in approval teal source && compile
    approval_program = compile_program(client, get_dump_approval())

    # Read in clear teal source && compile 
    clear_program = compile_program(client, get_dump_clear())

    global_schema = StateSchema(1,0)
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
