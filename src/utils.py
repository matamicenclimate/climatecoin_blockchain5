import base64


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