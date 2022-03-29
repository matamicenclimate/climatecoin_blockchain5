from algosdk import *
from algosdk.v2client import indexer
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *
from algosdk.encoding import checksum, encode_address

from src.contracts.climatecoin_vault_asc import get_approval, get_clear
from src.utils import compile_program, wait_for_confirmation


token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
# url = "http://localhost:4001"
url = "https://node.testnet.algoexplorerapi.io"
# indexer_url = "http://localhost:8980"
indexer_url = "https://algoindexer.testnet.algoexplorerapi.io"
deployer_mnemonic = "light tent note stool aware mother nice impulse chair tobacco rib mountain roof key crystal author sail rural divide labor session sleep neutral absorb useful"
random_user = "know tag story install insect good diagram crumble drop impact brush trash review endless border timber reflect machine ship pig sample ugly salad about act"
random_user_ONLY_ONCE = "laptop pink throw human job expect talent december erase base entry wear exile degree hole argue float under giraffe bid fold only shine above tooth"

deployed_app_id=80758140

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
    manager_pk = mnemonic.to_private_key(deployer_mnemonic)
    manager_addr = account.address_from_private_key(manager_pk)
    # manager_addr, manager_pk = get_accounts()[0]

    manager_signer = AccountTransactionSigner(manager_pk)
    print("Using {}".format(manager_addr))

    # Create app
    app_id = update_app(manager_addr, deployed_app_id, manager_pk)
    print("Updated App with id: {}".format(app_id))


def update_app(addr, app_id, pk):
    # Get suggested params from network
    sp = client.suggested_params()

    # Read in approval teal source && compile
    approval_program = compile_program(client, get_approval())

    # Read in clear teal source && compile
    clear_program = compile_program(client, get_clear())

    # Create the transaction
    create_txn = ApplicationUpdateTxn(addr, sp, app_id, approval_program, clear_program)

    # Sign it
    signed_txn = create_txn.sign(pk)

    # Ship it
    txid = client.send_transaction(signed_txn)

    # Wait for the result so we can return the app id
    result = wait_for_confirmation(client, txid)

    print(result)
    return result['application-index']


if __name__ == "__main__":
    demo()
