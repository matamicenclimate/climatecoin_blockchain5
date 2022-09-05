import time
import os
from algosdk.v2client import indexer
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from algosdk import util, mnemonic

from sandbox import get_accounts
from src.contracts.climatecoin_dump_asc import get_dump_approval, get_dump_clear

from src.contracts.climatecoin_vault_asc import get_approval, get_clear
from src.utils import get_asset_supply, print_asset_holding, get_dummy_metadata, get_asset_holding
from utils import compile_program, wait_for_confirmation

#################
# SCRIPT CONFIG #
#################
testnet = True
# delete the contracts when the script is done
delete_on_finish = False
# abort script after deploying and setting up the contracts
only_deploy = False
approve_burn = True
#################

token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
url = "http://localhost:4001"
url_testnet = "https://node.testnet.algoexplorerapi.io"
indexer_url = "http://localhost:8980"
indexer_url_testnet = "https://algoindexer.testnet.algoexplorerapi.io"

if testnet:
    url = url_testnet
    indexer_url = indexer_url_testnet

# this is the one we use in the BE
deployer_mnemonic = "shift zebra bean aunt sketch true finger trumpet scrap deputy manual bleak arch atom sustain link ship rifle sad garbage half assault phrase absent tuition"
deployer_mnemonic = "claim long sun pipe simple brick essay detail dash mass dose puzzle cash dream job invite motor casino rally vote honey grid simple able mystery"
print(f"REMEMBER USING BACKEND NEUMONIC {deployer_mnemonic}")
# some other random mnemonic
random_user = "page warfare excess stable avocado cushion mean cube prefer farm dog rally human answer amount same ticket speed sadness march jar estate engine abandon poverty"
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

with open("src/contracts/climatecoin_burn_asc.json") as f:
    burn_iface = Interface.from_json(f.read())


def get_method(i: Interface, name: str) -> Method:
    for m in i.methods:
        if m.name == name:
            return m
    raise Exception("No method with the name {}".format(name))


def demo():
    manager_addr = None
    manager_pk = None
    user_addr = None
    user_pk = None

    # Create acct
    if testnet:
        manager_pk = mnemonic.to_private_key(deployer_mnemonic)
        manager_addr = account.address_from_private_key(manager_pk)
    else:
        manager_add, manager_k = get_accounts()[0]
        manager_addr = manager_add
        manager_pk = manager_k

    manager_signer = AccountTransactionSigner(manager_pk)
    print("Using {}".format(manager_addr))

    # Create random user acct
    # Create acct
    if testnet:
        user_pk = mnemonic.to_private_key(random_user)
        user_addr = account.address_from_private_key(user_pk)
    else:
        user_add, user_k = get_accounts()[1]
        user_addr = user_add
        user_pk = user_k
    user_signer = AccountTransactionSigner(user_pk)
    print("Using {}".format(user_addr))

    #
    # Create apps
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

        # TODO: how many algos does this cost? do we have to up the fee?
        # cover account minimum algo balance to operate
        atc.add_transaction(
            TransactionWithSigner(
                txn=PaymentTxn(manager_addr, sp, vault_app_addr, util.algos_to_microalgos(30 if only_deploy else 1), None),
                signer=manager_signer
            )
        )
        atc.add_transaction(
            TransactionWithSigner(
                txn=PaymentTxn(manager_addr, sp, dump_app_addr, util.algos_to_microalgos(30 if only_deploy else 1), None),
                signer=manager_signer
            )
        )

        atc.add_method_call(vault_app_id, get_method(iface, "set_dump"), manager_addr, sp, manager_signer,
                            [dump_app_id])
        atc.add_method_call(dump_app_id, get_method(dump_iface, "set_vault_app"), manager_addr, sp, manager_signer,
                            [vault_app_id])
        atc.add_method_call(vault_app_id, get_method(iface, "mint_climatecoin"), manager_addr, sp, manager_signer, [], foreign_apps=[dump_app_id])

        result = atc.execute(client, 4)
        for res in result.abi_results:
            print(res.return_value)
        climatecoin_asa_id = result.abi_results[2].return_value

        if only_deploy:
            print(f"BACK:\n\nAPP_ID={vault_app_id}\nDUMP_APP_ID={dump_app_id}\nCLIMATECOIN_ASA_ID={climatecoin_asa_id}"
                  f"\n\n\nFRONT:\n\nREACT_APP_CLIMATECOIN_ASA_ID={climatecoin_asa_id}\nREACT_APP_SMART_CONTRACT_ID={vault_app_id}")
            raise Exception("Script halted after initial setup")

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
        for iter in [0]:
            sp = client.suggested_params()
            #
            # Mint  some nfts
            print(f"[ {iter} ] mint an NFT", )
            atc = AtomicTransactionComposer()
            sp.fee = sp.min_fee * 3
            # Dummy metadata
            metadata_json, encoded = get_dummy_metadata()
            nft_total_supply = 250

            atc.add_method_call(vault_app_id, get_method(iface, "mint_developer_nft"), manager_addr, sp, manager_signer,
                                [nft_total_supply, dump_app_id, dump_app_addr, 'http://s3.eu-west-3.amazonaws.com:80/climatecoin-ico/develop/pexels_lumn_167699_562d54b79b.jpg'], note=metadata_json.encode() )
            results = atc.execute(client, 4)

            created_nft_id = results.abi_results[-1].return_value
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
            # Move the NFT to the users wallet
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

        time.sleep(1.5)  # wait for the indexer to catch up
        climatecoins_to_burn = get_asset_holding(indexer_client, user_addr, climatecoin_asa_id)

        print("[ 3 ] Burn the climatecoins")
        atc = AtomicTransactionComposer()
        # add random nonce in note so we can send identicall txns

        sp = client.suggested_params()
        sp.fee = sp.min_fee * 3

        atc.add_transaction(
            TransactionWithSigner(
                txn=AssetTransferTxn(user_addr, sp, vault_app_addr, climatecoins_to_burn, climatecoin_asa_id), signer=user_signer
            )
        )
        # Send algos needed for the burn contract app to operate
        atc.add_transaction(
            TransactionWithSigner(
                txn=PaymentTxn(manager_addr, sp, vault_app_addr, util.algos_to_microalgos((2+len(minted_nfts))*0.1), None),
                signer=manager_signer
            )
        )
        atc.add_method_call(vault_app_id, get_method(iface, "burn_parameters"), manager_addr, sp, manager_signer,
                            foreign_assets=minted_nfts)
        atc.add_method_call(vault_app_id, get_method(iface, "burn_climatecoins"), user_addr, sp, user_signer,
                            accounts=[dump_app_addr], foreign_assets=minted_nfts+[climatecoin_asa_id], foreign_apps=[dump_app_id])
        atc.build_group()
        result = atc.execute(client, 4)
        for res in result.abi_results:
            print(res.return_value)

        burn_contract_id = result.abi_results[1].tx_info['inner-txns'][0]['application-index']

        print("[ 3 ] Minted nft ids")
        print(minted_nfts)

        print("[ 3 ] Final balances")
        time.sleep(1.5)  # wait for the indexer to catch up
        print_asset_holding(indexer_client, user_addr, climatecoin_asa_id, "user - climatecoin")
        print_asset_holding(indexer_client, vault_app_addr, climatecoin_asa_id, "app - climatecoin")

        if approve_burn:
            print("[ 4 ] Approve burn")
            atc = AtomicTransactionComposer()
            metadata_json, encoded = get_dummy_metadata()

            atc.add_method_call(vault_app_id, get_method(iface, "mint_compensation_nft"), manager_addr, sp, manager_signer,
                                note=metadata_json.encode() )
            result = atc.execute(client, 4)
            for res in result.abi_results:
                print(res.return_value)

            compensation_nft_id = result.abi_results[0].return_value

            atc = AtomicTransactionComposer()

            # Approve the burn
            atc.add_method_call(vault_app_id, get_method(iface, "approve_burn"),
                                manager_addr, sp, manager_signer,
                                [burn_contract_id, compensation_nft_id],
                                foreign_assets=minted_nfts+[climatecoin_asa_id],
                                foreign_apps=[dump_app_id],
                                accounts=[dump_app_addr, user_addr])

            atc.execute(client, 4)

            atc = AtomicTransactionComposer()

            # User optin to compensation nft
            atc.add_transaction(
                TransactionWithSigner(
                    txn=AssetTransferTxn(user_addr, sp, user_addr, 0, compensation_nft_id), signer=user_signer
                )
            )

            # Approve the burn
            atc.add_method_call(vault_app_id, get_method(iface, "send_burn_nft_certificate"),
                                manager_addr, sp, manager_signer,
                                [burn_contract_id, compensation_nft_id],
                                accounts=[user_addr])

            atc.execute(client, 4)
        else:
            print("[ 4 ] Reject burn")
            atc = AtomicTransactionComposer()

            # Reject the burn
            atc.add_method_call(vault_app_id, get_method(iface, "reject_burn"),
                                manager_addr, sp, manager_signer,
                                [burn_contract_id],
                                foreign_assets=minted_nfts + [climatecoin_asa_id],
                                foreign_apps=[dump_app_id],
                                accounts=[dump_app_addr, user_addr])

            atc.execute(client, 4)

        for i in range(len(minted_nfts)):
            nft_id = minted_nfts[i]
            print_asset_holding(indexer_client, dump_app_addr, nft_id, f"dump - nft {i}")

    except Exception as e:
        print(e)
        
    finally:
        if delete_on_finish:
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
    create_txn = ApplicationCreateTxn(addr, sp, 0, approval_program, clear_program, global_schema, local_schema, extra_pages=1)

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
