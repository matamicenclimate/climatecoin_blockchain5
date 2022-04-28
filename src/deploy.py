import os
from algosdk.v2client import indexer
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from algosdk.encoding import checksum, encode_address
from algosdk import util

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

    dump_addr, dump_pk = get_accounts()[2]
    dump_signer = AccountTransactionSigner(dump_pk)
    print("Using {}".format(dump_addr))

    #
    # Create app
    app_id = create_app(manager_addr, manager_pk)
    print("Created App with id: {}".format(app_id))

    app_addr = logic.get_application_address(app_id)
    print("Application Address: {}".format(app_addr))

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
                txn=PaymentTxn(manager_addr, sp, get_escrow_from_app(app_id), util.algos_to_microalgos(1), None),
                signer=manager_signer
            )
        )

        atc.add_method_call(app_id, get_method(iface, "mint_climatecoin"), manager_addr, sp, manager_signer, [])
        atc.add_method_call(app_id, get_method(iface, "set_minter_address"), manager_addr, sp, manager_signer,
                            [manager_addr])
        atc.add_method_call(app_id, get_method(iface, "set_dump"), manager_addr, sp, manager_signer,
                            [dump_app_id])
        # atc.add_method_call(app_id, get_method(iface, "set_oracle_address"), addr, sp, addr_signer, [oracle_addr])

        result = atc.execute(client, 4)
        for res in result.abi_results:
            print(res.return_value)
        climatecoin_asa_id = result.abi_results[0].return_value

        #
        # Rekey dump to smart contract so that we can perform opt-ins from the SC
        # print("[ 0 ] rekeying dump to smart contract")
        # atc = AtomicTransactionComposer()
        # atc.add_transaction(
        #     TransactionWithSigner(
        #         txn=PaymentTxn(dump_addr, sp, dump_addr, 0, rekey_to=get_escrow_from_app(app_id)), signer=dump_signer
        #     )
        # )
        # atc.execute(client, 2) 

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

        #
        # Mint  some nfts
        print("[ 0 ] mint an NFT")
        sp = client.suggested_params()
        atc = AtomicTransactionComposer()
        # Dummy metadata
        metadata_json, encoded = get_dummy_metadata()
        nft_total_supply = 250

        atc.add_method_call(app_id, get_method(iface, "create_nft"), manager_addr, sp, manager_signer,
                            [nft_total_supply, dump_addr], note=metadata_json.encode())
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
        atc.execute(client, 2)

        #
        # Move the NFT to the users waller
        print("[ 1 ] Manager calling move method")
        tokens_to_move = get_asset_supply(indexer_client, created_nft_id)
        print(tokens_to_move)
        atc = AtomicTransactionComposer()
        atc.add_method_call(
            app_id,
            get_method(iface, "move"),
            manager_addr,
            sp,
            manager_signer,
            [created_nft_id, get_escrow_from_app(app_id), user_addr, tokens_to_move],
        )
        atc.execute(client, 2)
        print_asset_holding(indexer_client, user_addr, created_nft_id, "user - nft")

        print("[ 1 ] Dump optin to NFT")
        # atc = AtomicTransactionComposer()
        # atc.add_transaction(
        #     TransactionWithSigner(
        #         txn=AssetTransferTxn(dump_addr, sp, dump_addr, 0, created_nft_id), signer=dump_signer
        #     )
        # )
        # atc.execute(client, 2)

        #
        # Print the initial asset holdings
        print("[ 1 ] Initial holdings")
        print_asset_holding(indexer_client, user_addr, created_nft_id, "user - nft")
        print_asset_holding(indexer_client, user_addr, climatecoin_asa_id, "user - climatecoin")

        #
        # Swap them
        print("[ 1 ] User swaps the asset")
        atc = AtomicTransactionComposer()
        # add random nonce in note so we can send identicall txns
        atc.add_method_call(app_id, get_method(iface, "unfreeze_nft"), user_addr, sp, user_signer,
                            [created_nft_id], note=os.urandom(1))
        atc.add_transaction(
            TransactionWithSigner(
                txn=AssetTransferTxn(user_addr, sp, get_escrow_from_app(app_id), tokens_to_move, created_nft_id), signer=user_signer
            )
        )
        atc.add_method_call(app_id, get_method(iface, "swap_nft_to_fungible"), user_addr, sp, user_signer,
                            [created_nft_id], foreign_assets=[climatecoin_asa_id], note=os.urandom(1))
        atc.build_group()
        atc.execute(client, 4)

        #
        # Print the final asset holdings
        print("[ 1 ] Final holdings")
        print_asset_holding(indexer_client, user_addr, created_nft_id, "user - nft")
        print_asset_holding(indexer_client, user_addr, climatecoin_asa_id, "user - climatecoin")

        climatecoins_to_burn = get_asset_holding(indexer_client, user_addr, climatecoin_asa_id)

        #
        # Burn the climatecoins
        # atc = AtomicTransactionComposer()
        # print(f"[ 1 ] User burns the Climatecoins {climatecoins_to_burn}")
        # # add random nonce in note so we can send identicall txns
        # atc.add_transaction(
        #     TransactionWithSigner(
        #         txn=AssetTransferTxn(user_addr, sp, get_escrow_from_app(app_id), climatecoins_to_burn, climatecoin_asa_id),
        #         signer=user_signer
        #     )
        # )
        # # TODO:
        # # call the burn method with the list of NFT's that will be sent to the burn address
        # atc.add_method_call(app_id, get_method(iface, "burn_climatecoins"), manager_addr, sp, manager_signer,
        #                     [created_nft_id], accounts=[dump_addr], note=os.urandom(1))
        # atc.build_group()
        # atc.execute(client, 4)
        # print_asset_holding(indexer_client, user_addr, created_nft_id)
        # print_asset_holding(indexer_client, user_addr, climatecoin_asa_id)

        print("[ 1 ] App's nft balance")
        print_asset_holding(indexer_client, get_escrow_from_app(app_id), created_nft_id, "app - nft")

    except Exception as e:
        print(e)
        
    finally:
        #
        # Delete app so we dont reach the limit of apps per account whilst testing
        atc = AtomicTransactionComposer()
        atc.add_transaction(
            TransactionWithSigner(
                txn=ApplicationDeleteTxn(manager_addr, sp, app_id), signer=manager_signer
            )
        )
        atc.add_transaction(
            TransactionWithSigner(
                txn=ApplicationDeleteTxn(manager_addr, sp, dump_app_id), signer=manager_signer
            )
        )
        atc.execute(client, 4)
        print(f"{app_id} was succesfully deleted")
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
