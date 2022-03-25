from email.headerregistry import Address
from algosdk import *
from algosdk.v2client import algod
from algosdk.v2client.models import DryrunSource, DryrunRequest
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *
from algosdk.abi import *

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


def demo():
    # Create acct
    # pk = mnemonic.to_private_key(deployer_mnemonic)
    # addr = account.address_from_private_key(pk)
    addr, pk = get_accounts()[0]
    print("Using {}".format(addr))

    # Create app
    app_id = create_app(addr, pk)
    print("Created App with id: {}".format(app_id))

    app_addr = logic.get_application_address(app_id)
    print("Application Address: {}".format(app_addr))

    atc = AtomicTransactionComposer()
    signer = AccountTransactionSigner(pk)
    sp = client.suggested_params()
    print(mint_climatecoin_selector.methodName)

    app_call_txn = get_app_call(addr, sp, app_id, [get_method(iface, "mint_climatecoin"), "Climatecoin", "CC"])
    tws = TransactionWithSigner(app_call_txn, signer)
    atc.add_transaction(tws)
    
    result = atc.execute(client, 4)
    for res in result.abi_results:
        print(res.return_value)


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

    global_schema = StateSchema(2, 1)
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