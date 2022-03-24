# VRF contract example
# https://github.com/ori-shem-tov/vrf-oracle/blob/vrf-teal5/pyteal/teal5.py

from pyteal import *
import dataclasses
from algosdk import encoding
from base64 import b32encode, b64encode, b64decode

TEAL_VERSION = 6

# Schema
ORACLE_GLOBAL_BYTES = 1
ORACLE_GLOBAL_INTS = 1
ORACLE_LOCAL_BYTES = 0
ORACLE_LOCAL_INTS = 0

# Global Vars
GLOBAL_NFT_MINTER_ADDRESS=Bytes('nft_minter_address')
GLOBAL_CLIMATECOIN_ASA_ID=Bytes('climatecoin_asa_id')


def ct_oracle_clear():
    return Seq([
        Approve()
    ])

def ct_oracle_clear_asc1():
    return compileTeal(ct_oracle_clear(), Mode.Application, version=TEAL_VERSION)


def ct_oracle():

    def initialize_oracle():
        return Seq([
            Approve()
        ])

    #  the fee payment transactions is always 1 transaction before the application call
    payment_txn = Gtxn[Txn.group_index() - Int(1)]

    mint_climatecoin = Seq([
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                # TxnField.receiver: App.globalGet(GLOBAL_OWNER_ADDRESS),
                TxnField.amount: Int(0),
                TxnField.fee: Int(0),
                TxnField.application_id: App.globalGet(LOCAL_CALLBACK_CONTRACT_ID)
            }
        ),
        InnerTxnBuilder.Submit(),
        Int(1)
    ]) 

    set_minter_address = Seq([
        Int(1)
    ])

    swap_nft_for_climatecoin = Seq([
        Int(1)
    ])

    handle_noop = Cond(
        [Txn.application_args[0] == Bytes('request'), Return(request)],
        [Txn.application_args[0] == Bytes('respond'), (respond)],
        [Txn.application_args[0] == Bytes('set_callback'), Approve()],
        [Txn.application_args[0] == Bytes('cancel'), (cancel)],
    )

    program = Cond(
        #  handle app creation
        [Txn.application_id() == Int(0), initialize_oracle(cfg)],
        #  allow all to opt-in and close-out
        [Txn.on_completion() == OnComplete.OptIn, Approve()],
        [Txn.on_completion() == OnComplete.CloseOut, ct_oracle_clear()],
        #  allow creator to update and delete app
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop]
    )

    return compileTeal(program, Mode.Application, version=TEAL_VERSION)


if __name__ == '__main__':
    filename = 'ct_oracle.teal'
    with open(filename, 'w') as f:
        compiled = ct_oracle()
        f.write(compiled)
        print(f'compiled {filename}')

    filename = 'ct_oracle_clear.teal'
    with open(filename, 'w') as f:
        compiled = ct_oracle_clear()
        f.write(compiled)
        print(f'compiled {filename}')