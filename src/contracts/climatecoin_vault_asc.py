# VRF contract example
# https://github.com/ori-shem-tov/vrf-oracle/blob/vrf-teal5/pyteal/teal5.py

from pyteal import *

from src.pyteal_utils import ensure_opted_in, clawback_asset

TEAL_VERSION = 6

return_prefix = Bytes("base16", "0x151f7c75")  # Literally hash('return')[:4]

# Global Vars
NFT_MINTER_ADDRESS=Bytes('nft_minter_address')
ORACLE_ADDRESS=Bytes('oracle_address')
CLIMATECOIN_ASA_ID=Bytes('climatecoin_asa_id')
MINT_FEE=Bytes('nft_mint_fee')


create_selector = MethodSignature(
    "create_nft(uint64)uint64"
)
@Subroutine(TealType.uint64)
def create_nft():
    amount = Btoi(Txn.application_args[1])
    total = Mul(Div(amount, Int(100)), Minus(Int(100), App.globalGet(MINT_FEE)))
    fee = Mul(Div(amount, Int(100)), App.globalGet(MINT_FEE))

    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_name: Bytes("CO2TONNE@ARC69"),
                TxnField.config_asset_unit_name: Bytes("CO2"),
                TxnField.config_asset_total: fee,
                TxnField.config_asset_decimals: Int(0),
                TxnField.config_asset_manager: Global.current_application_address(),
                TxnField.config_asset_reserve: Global.current_application_address(),
                TxnField.config_asset_freeze: Global.current_application_address(),
                TxnField.config_asset_clawback: Global.current_application_address(),
                TxnField.config_asset_default_frozen: Int(1),
                TxnField.note: Txn.note()
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_name: Bytes("CO2TONNE@ARC69"),
                TxnField.config_asset_unit_name: Bytes("CO2"),
                TxnField.config_asset_total: total,
                TxnField.config_asset_decimals: Int(0),
                TxnField.config_asset_manager: Global.current_application_address(),
                TxnField.config_asset_reserve: Global.current_application_address(),
                TxnField.config_asset_freeze: Global.current_application_address(),
                TxnField.config_asset_clawback: Global.current_application_address(),
                TxnField.config_asset_default_frozen: Int(1),
                TxnField.note: Txn.note()
            }
        ),
        InnerTxnBuilder.Submit(),
        Log(Concat(return_prefix, Itob(InnerTxn.created_asset_id()))),
        Int(1),
    )

swap_nft_to_fungible_selector = MethodSignature(
    "swap_nft_to_fungible(asset)uint64"
)
@Subroutine(TealType.uint64)
def swap_nft_to_fungible():
    asset_id = Txn.assets[Btoi(Txn.application_args[1])]

    valid_swap = Seq([
        Assert(Global.group_size() == Int(1)),
        #  this application serves as the escrow for the fee
        # Assert(transfer_txn.xfer_asset() == Btoi(Txn.application_args[1])),
        # Assert(payment_txn.type_enum() == TxnType.Payment),
        # Assert(payment_txn.amount() == App.globalGet(GLOBAL_SERVICE_FEE)),
    ])

    return Seq(
        valid_swap,
        ensure_opted_in(asset_id),
        # clawback all the asset and exposes InnerTxn.asset_amount() to mint some climatecoins
        clawback_asset(asset_id, Txn.sender()),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: App.globalGet(CLIMATECOIN_ASA_ID),
                TxnField.asset_amount: InnerTxn.asset_amount(),
                TxnField.asset_receiver: Txn.sender(),
            }
        ),
        InnerTxnBuilder.Submit(),
        Int(1)
    )

mint_climatecoin_selector = MethodSignature(
    "mint_climatecoin()uint64"
)
@Subroutine(TealType.uint64)
def mint_climatecoin():
    return Seq(
        InnerTxnBuilder.Begin(),
        # This method accepts a dictionary of TxnField to value so all fields may be set 
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_name: Bytes("Climatecoin"),
            TxnField.config_asset_unit_name: Bytes("CC"),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_reserve: Global.current_application_address(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_total: Int(150_000_000_000),
            TxnField.config_asset_decimals: Int(0),
            TxnField.fee: Int(50),
        }),
        # Submit the transaction we just built
        InnerTxnBuilder.Submit(),
        App.globalPut(CLIMATECOIN_ASA_ID, InnerTxn.created_asset_id()),
        Log(Concat(return_prefix, Itob(InnerTxn.created_asset_id()))),
        Int(1)
    )

set_minter_address_selector = MethodSignature(
    "set_minter_address(address)address"
)
@Subroutine(TealType.uint64)
def set_minter_address():
    return Seq(
        App.globalPut(NFT_MINTER_ADDRESS, Txn.application_args[1]),
        Log(Concat(return_prefix, Txn.application_args[1])),
        Int(1)
    )


set_fee_selector = MethodSignature(
    "set_fee_selector(uint64)uint64"
)
@Subroutine(TealType.uint64)
def set_fee():
    return Seq(
        App.globalPut(MINT_FEE, Txn.application_args[1]),
        Log(Concat(return_prefix, Txn.application_args[1])),
        Int(1)
    )

move_selector = MethodSignature(
    "move(asset,account,account,uint64)void"
)
@Subroutine(TealType.uint64)
def move():
    asset_id = Txn.assets[Btoi(Txn.application_args[1])]
    from_acct = Txn.accounts[Btoi(Txn.application_args[2])]
    to_acct = Txn.accounts[Btoi(Txn.application_args[3])]
    amount = Btoi(Txn.application_args[4])
    return Seq(move_asset(asset_id, from_acct, to_acct, amount), Int(1))

@Subroutine(TealType.none)
def move_asset(asset_id, owner, buyer, amount):
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: asset_id,
                TxnField.asset_amount: amount,
                TxnField.asset_sender: owner,
                TxnField.asset_receiver: buyer,
            }
        ),
        InnerTxnBuilder.Submit(),
    )

def contract():
    def initialize_vault():
        return Seq(
            App.globalPut(CLIMATECOIN_ASA_ID, Int(0)),
            App.globalPut(MINT_FEE, Int(5)),            
            Int(1)
        )

    from_creator = Txn.sender() == Global.creator_address()

    handle_noop = Cond(
        [And(Txn.application_args[0] == mint_climatecoin_selector, from_creator), mint_climatecoin()],
        [And(Txn.application_args[0] == set_minter_address_selector, from_creator), set_minter_address()],
        [And(Txn.application_args[0] == move_selector, from_creator), move()],
        [And(Txn.application_args[0] == create_selector, from_creator), create_nft()],
        [And(Txn.application_args[0] == set_fee_selector, from_creator), set_fee()],
        [Txn.application_args[0] == swap_nft_to_fungible_selector, swap_nft_to_fungible()],
    )

    return Cond(
        #  handle app creation
        [Txn.application_id() == Int(0), Return(initialize_vault())],
        #  allow all to opt-in and close-out
        [Txn.on_completion() == OnComplete.OptIn, Reject()],
        [Txn.on_completion() == OnComplete.CloseOut, Reject()],
        #  allow creator to update and delete app
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.NoOp, Return(handle_noop)]
    )


def clear():
    return Approve()


def get_approval():
    return compileTeal(contract(), mode=Mode.Application, version=6)


def get_clear():
    return compileTeal(clear(), mode=Mode.Application, version=6)


if __name__ == "__main__":
    print(get_approval())