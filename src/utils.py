import base64
import json

def compile_program(algod_client, source_code):
    compile_response = algod_client.compile(source_code)
    return base64.b64decode(compile_response["result"])

def wait_for_confirmation(client, txid):
    """
    Utility function to wait until the transaction is confirmed before
    proceeding.
    """
    last_round = client.status().get("last-round")
    txinfo = client.pending_transaction_info(txid)

    while not txinfo.get("confirmed-round", -1) > 0:
        print(f"Waiting for transaction {txid} confirmation.")
        last_round += 1
        client.status_after_block(last_round)
        txinfo = client.pending_transaction_info(txid)

    print(f"Transaction {txid} confirmed in round {txinfo.get('confirmed-round')}.")
    return txinfo


def print_asset_holding(myindexer, account, assetid, label):
    response = myindexer.asset_balances(asset_id = assetid)

    for balance in response["balances"]:
        if balance["address"] == account:
            print(f"account {account} - {label}; asset {assetid}; balance: {balance['amount']}")
            break

def get_asset_holding(myindexer, account, assetid):
    response = myindexer.asset_balances(asset_id = assetid)
    # print(response)
    for balance in response["balances"]:
        if balance["address"] == account:
            return balance["amount"]


def get_asset_supply(myindexer, assetid):
    response = myindexer.asset_info(asset_id = assetid)
    print(response)
    return response["asset"]["params"]["total"]

def get_dummy_metadata():
    metadata = {
        "standard": "arc-69",
        "description": "Carbon Document@arc69",
        "external_url": "https://www.climatetrade.com/assets/....yoquese.pdf",
        "mime_type": "file/pdf",
        "properties": {
            "Serial_Number": "12345-09876-456",
            "Provider": "Verra"
        }
    }

    metadata_json = json.dumps(metadata)
    encoded = base64.encodebytes(metadata_json.encode()).decode('ascii')

    return metadata_json, encoded