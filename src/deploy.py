from email.headerregistry import Address
from algosdk import *
from algosdk.v2client import algod
from algosdk.v2client.models import DryrunSource, DryrunRequest
from algosdk.future.transaction import *
from algosdk.atomic_transaction_composer import *

from sandbox import get_accounts

from climatecoin_vault_asc import mint_climatecoin_selector, contract, contract_clear
from utils import compile_program, wait_for_confirmation

token = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
url = "http://localhost:4001"
# url = "https://node.testnet.algoexplorerapi.io"
deployer_mnemonic = "reward remove stairs topic disorder town prison town angry gas tray home obvious biology distance belt champion human rotate coin antique gospel grit ability game"

client = algod.AlgodClient(token, url)

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
    app_call_txn = get_app_call(addr, sp, app_id, [mint_climatecoin_selector.methodName, "Climatecoin", "CC", (150_000_000).to_bytes(8,'big')])
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

    # We dont need no stinkin storage
    schema = StateSchema(2, 1)

    # Create the transaction
    create_txn = ApplicationCreateTxn(addr, sp, 0, approval_program, clear_program, schema, schema)

    # Sign it
    signed_txn = create_txn.sign(pk)

    # Ship it
    txid = client.send_transaction(signed_txn)
    
    # Wait for the result so we can return the app id
    result = wait_for_confirmation(client, txid)

    return result['application-index']

if __name__ == "__main__":
    demo()