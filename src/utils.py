from pyteal import *

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
