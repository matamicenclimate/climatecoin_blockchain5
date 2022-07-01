from pyteal import *

amount_key = Bytes("amount")

from_creator = Txn.sender() == Global.creator_address()
router = Router(
    "climatecoin_burn",
    BareCallActions(
        no_op=OnCompleteAction.create_only(Approve()),
        delete_application=OnCompleteAction.always(Return(from_creator)),
        update_application=OnCompleteAction.always(Return(from_creator)),
        opt_in=OnCompleteAction.always(Reject()),
        close_out=OnCompleteAction.always(Reject()),
        clear_state=OnCompleteAction.call_only(Reject()),
    ),
)


@router.method
def set_amt(amt: abi.Uint64):
    return Seq(
        App.globalPut(amount_key, Mul(amt.get(), Int(10))),
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
