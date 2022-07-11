from pyteal import *

USER_ADDRESS_KEY = Bytes("user_add")
DUMP_ADDRESS_KEY = Bytes("dump_add")
CLIMATECOIN_ASSET_ID_KEY = Bytes("cc_id")

CC_NFT_ASSET_UNIT_NAME = Bytes("CC")
COMPENSATION_NFT_ASSET_UNIT_NAME = Bytes("BUYCO2")
return_prefix = Bytes("base16", "0x151f7c75")

from_creator = Txn.sender() == Global.creator_address()


@Subroutine(TealType.none)
def set_up():
    return Seq(
        App.globalPut(USER_ADDRESS_KEY, Txn.accounts[1]),
        App.globalPut(DUMP_ADDRESS_KEY, Txn.accounts[2])
    )


@Subroutine(TealType.none)
def close_app():
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.close_remainder_to: Global.creator_address(),
            TxnField.fee: Int(0)
        }),
        InnerTxnBuilder.Submit()
    )


@Subroutine(TealType.none)
def send_asset(asset_id, receiver_add, amount):
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: asset_id,
                TxnField.asset_amount: amount,
                TxnField.asset_receiver: receiver_add,
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),
    )


@Subroutine(TealType.none)
def close_asset(asset_id, receiver_add):
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: asset_id,
                TxnField.asset_close_to: receiver_add,
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),
    )


@Subroutine(TealType.none)
def do_optin(asset_id):
    return send_asset(asset_id, Global.current_application_address(), Int(0))


router = Router(
    "climatecoin_burn",
    BareCallActions(
        no_op=OnCompleteAction.create_only(Seq(set_up(), Approve())),
        delete_application=OnCompleteAction.always(Return(from_creator)),
        update_application=OnCompleteAction.always(Return(from_creator)),
        opt_in=OnCompleteAction.always(Reject()),
        close_out=OnCompleteAction.always(Reject()),
        clear_state=OnCompleteAction.call_only(Reject()),
    ),
)


@router.method
def approve():
    i = ScratchVar(TealType.uint64)
    return Seq(
        Assert(from_creator),
        For(i.store(Int(0)), i.load() < Txn.assets.length(), i.store(Add(i.load(), Int(1)))).Do(
            Seq(
                asset_unit_name := AssetParam.unitName(Txn.assets[i.load()]),
                If(asset_unit_name.value() == COMPENSATION_NFT_ASSET_UNIT_NAME)
                .Then(
                    Seq(
                        do_optin(Txn.assets[i.load()]),
                        close_asset(Txn.assets[i.load()], Global.creator_address())
                    )
                )
                .Else(close_asset(Txn.assets[i.load()], App.globalGet(DUMP_ADDRESS_KEY)))
            )
        ),
        close_app()
    )


@router.method
def reject():
    i = ScratchVar(TealType.uint64)
    return Seq(
        Assert(from_creator),
        For(i.store(Int(0)), i.load() < Txn.assets.length(), i.store(Add(i.load(), Int(1)))).Do(
            Seq(
                If(Txn.assets[i.load()] == App.globalGet(CLIMATECOIN_ASSET_ID_KEY))
                .Then(close_asset(Txn.assets[i.load()], App.globalGet(USER_ADDRESS_KEY)))
                .Else(close_asset(Txn.assets[i.load()], Global.creator_address()))
            )
        ),
        close_app()
    )


@router.method
def opt_in(asset: abi.Asset):
    asset_unit_name = AssetParam.unitName(asset.asset_id())
    asset_creator = AssetParam.creator(asset.asset_id())

    return Seq(
        asset_unit_name,
        asset_creator,
        Assert(And(from_creator, asset_creator.value() == Global.creator_address())),
        do_optin(asset.asset_id()),

        If(asset_unit_name.value() == CC_NFT_ASSET_UNIT_NAME,
           App.globalPut(CLIMATECOIN_ASSET_ID_KEY, asset.asset_id()))
    )


approval, clear, contract = router.compile_program(
    version=6
)


def get_burn_approval():
    return approval


def get_burn_clear():
    return clear


def get_burn_contract():
    return contract


if __name__ == "__main__":
    import json

    with open("climatecoin_burn_asc.json", "w") as f:
        f.write(json.dumps(contract.dictify(), indent=4))

    print(approval)
    print("-------")
    print(clear)
