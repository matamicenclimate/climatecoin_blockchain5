from pyteal import *

USER_ADDRESS_KEY = Bytes("user_add")
CLIMATECOIN_ASSET_ID_KEY = Bytes("cc_id")

CC_NFT_ASSET_UNIT_NAME = Bytes("CC")
return_prefix = Bytes("base16", "0x151f7c75")

from_creator = Txn.sender() == Global.creator_address()


@Subroutine(TealType.none)
def set_up():
    return App.globalPut(USER_ADDRESS_KEY, Txn.accounts[1])


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
def opt_in(asset: abi.Asset):
    asset_unit_name = AssetParam.unitName(asset.asset_id())
    asset_creator = AssetParam.creator(asset.asset_id())

    return Seq(
        asset_unit_name,
        asset_creator,
        Assert(And(from_creator, asset_creator.value() == Global.creator_address())),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: asset.asset_id(),
                TxnField.asset_amount: Int(0),
                TxnField.asset_receiver: Global.current_application_address(),
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Submit(),

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
