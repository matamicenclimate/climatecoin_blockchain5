# VRF contract example
# https://github.com/ori-shem-tov/vrf-oracle/blob/vrf-teal5/pyteal/teal5.py

from pyteal import *

from src.pyteal_utils import ensure_opted_in, clawback_asset, div_ceil

TEAL_VERSION = 6

return_prefix = Bytes("base16", "0x151f7c75")  # Literally hash('return')[:4]

# Global Vars
DUMP_ADDRESS=Bytes('dump_address')
VAULT_APP_ADDRESS=Bytes('vault_app_id')

do_optin_selector = MethodSignature(
    "do_optin(asset)void"
)
@Subroutine(TealType.uint64)
def do_optin():
    asset_id = Txn.assets[Btoi(Txn.application_args[1])]
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: asset_id,
                TxnField.asset_amount: Int(0),
                TxnField.asset_receiver: Global.current_application_address,
            }
        ),
        InnerTxnBuilder.Submit(),
        Int(1)
    )

set_vault_address_selector = MethodSignature(
    "set_vault_app(uint64)void"
)
@Subroutine(TealType.none)
def set_vault_address():
    return Seq(
        App.globalPut(VAULT_APP_ADDRESS, Txn.application_args[1]),
        Int(1)
    )


def contract():
    from_creator = Txn.sender() == Global.creator_address()
    # only accept innerTxns from other contracts
    from_vault = Global.caller_app_id() == App.globalGet(VAULT_APP_ADDRESS)

    handle_noop = Cond(
        [And(Txn.application_args[0] == do_optin_selector, from_vault), do_optin()],
        [And(Txn.application_args[0] == set_vault_address_selector, from_creator), set_vault_address()],
    )

    return Cond(
        #  handle app creation
        [Txn.application_id() == Int(0), Return(Int(1))],
        #  disallow all to opt-in and close-out
        [Txn.on_completion() == OnComplete.OptIn, Reject()],
        [Txn.on_completion() == OnComplete.CloseOut, Reject()],
        #  allow creator to update and delete app
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.NoOp, Return(handle_noop)]
    )


def clear():
    return Return(Int(1))


def get_dump_approval():
    return compileTeal(contract(), mode=Mode.Application, version=6)


def get_dump_clear():
    return compileTeal(clear(), mode=Mode.Application, version=6)


if __name__ == "__main__":
    print(get_dump_approval())