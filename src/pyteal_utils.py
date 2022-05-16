from pyteal import *

@Subroutine(TealType.none)
def clawback_asset(asset_id, owner):
    bal = AssetHolding.balance(owner, asset_id)

    return Seq(
        bal,
        If(
            bal.hasValue(),
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.AssetTransfer,
                        TxnField.xfer_asset: asset_id,
                        TxnField.asset_amount: bal.value(),
                        TxnField.asset_sender: owner,
                        TxnField.asset_receiver: Global.current_application_address(),
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        )
    )

@Subroutine(TealType.none)
def aoptin(reciever, aid):
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: aid,
                TxnField.asset_receiver: reciever,
            }
        ),
        InnerTxnBuilder.Submit(),
    )

@Subroutine(TealType.uint64)
def max(a, b) -> Expr:
    """max returns the max of 2 integers"""
    return If(a > b, a, b)


@Subroutine(TealType.uint64)
def min(a, b) -> Expr:
    """min returns the min of 2 integers"""
    return If(a < b, a, b)

@Subroutine(TealType.uint64)
def div_ceil(a, b) -> Expr:
    """Returns the result of division rounded up to the next integer
    Args:
        a: uint64 numerator for the operation
        b: uint64 denominator for the operation
    Returns:
        uint64 result of a truncated division + 1
    """
    q = a / b
    return If(a % b > Int(0), q + Int(1), q)

@Subroutine(TealType.none)
def ensure_opted_in(asset_id):
    bal = AssetHolding.balance(Global.current_application_address(), asset_id)
    return Seq(
        bal,
        If(
            Not(bal.hasValue()),
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.AssetTransfer,
                        TxnField.xfer_asset: asset_id,
                        TxnField.asset_amount: Int(0),
                        TxnField.asset_receiver: Global.current_application_address(),
                    }
                ),
                InnerTxnBuilder.Submit(),
            ),
        ),
    )

@Subroutine(TealType.none)
def axfer(reciever, aid, amt):
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: aid,
                TxnField.asset_amount: amt,
                TxnField.asset_receiver: reciever,
                TxnField.sender: Global.current_application_address()
            }
        ),
        InnerTxnBuilder.Submit(),
    )