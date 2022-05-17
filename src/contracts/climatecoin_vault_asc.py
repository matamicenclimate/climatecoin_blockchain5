# VRF contract example
# https://github.com/ori-shem-tov/vrf-oracle/blob/vrf-teal5/pyteal/teal5.py

from pyteal import *

from src.pyteal_utils import ensure_opted_in, min, div_ceil
from src.contracts.climatecoin_dump_asc import do_optin_selector
TEAL_VERSION = 6

return_prefix = Bytes("base16", "0x151f7c75")  # Literally hash('return')[:4]

# Global Vars
NFT_MINTER_ADDRESS=Bytes('nft_minter_address')
ORACLE_ADDRESS=Bytes('oracle_address')
CLIMATECOIN_ASA_ID=Bytes('climatecoin_asa_id')
MINT_FEE=Bytes('nft_mint_fee')
TOTAL_COINS_BURNED=Bytes('total_coins_burned')
DUMP_APP_ID=Bytes('dump_app_id')


create_selector = MethodSignature(
    "create_nft(uint64,application,account)uint64"
)
@Subroutine(TealType.uint64)
def create_nft():
    #
    multiplier = Int(1000)
    amount = Mul(Btoi(Txn.application_args[1]), multiplier)

    total = Mul(Div(amount, Int(100)), Minus(Int(100), App.globalGet(MINT_FEE)))
    fee = Mul(Div(amount, Int(100)), App.globalGet(MINT_FEE))

    normalize_total = Div(total, multiplier)
    normalize_fee = div_ceil(fee, multiplier)

    dump_address = Sha512_256(
        Concat(Bytes("appID"), Itob(App.globalGet(DUMP_APP_ID)))
    )

    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_name: Bytes("CO2TONNE@ARC69"),
                TxnField.config_asset_unit_name: Bytes("CO2"),
                TxnField.config_asset_total: normalize_fee,
                TxnField.config_asset_decimals: Int(0),
                TxnField.config_asset_manager: Global.current_application_address(),
                TxnField.config_asset_reserve: dump_address,
                TxnField.config_asset_freeze: Global.current_application_address(),
                TxnField.config_asset_clawback: Global.current_application_address(),
                TxnField.config_asset_default_frozen: Int(1),
                TxnField.note: Txn.note()
            }
        ),
        InnerTxnBuilder.Submit(),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(DUMP_APP_ID),
                # Pass the selector as the first arg to trigger the `echo` method
                TxnField.application_args: [
                    do_optin_selector, 
                    Itob(Int(0))  # first item in assets array
                ],
                TxnField.assets: [InnerTxn.created_asset_id()],
                # Set fee to 0 so caller has to cover it
                TxnField.fee: Int(0),
            }
        ),
        InnerTxnBuilder.Submit(),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_name: Bytes("CO2TONNE@ARC69"),
                TxnField.config_asset_unit_name: Bytes("CO2"),
                TxnField.config_asset_total: normalize_total,
                TxnField.config_asset_decimals: Int(0),
                TxnField.config_asset_manager: Global.current_application_address(),
                TxnField.config_asset_reserve: dump_address,
                TxnField.config_asset_freeze: Global.current_application_address(),
                TxnField.config_asset_clawback: Global.current_application_address(),
                TxnField.config_asset_default_frozen: Int(1),
                TxnField.note: Txn.note()
            }
        ),
        InnerTxnBuilder.Submit(),
        Log(Concat(return_prefix, Itob(InnerTxn.created_asset_id()))),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(DUMP_APP_ID),
                # Pass the selector as the first arg to trigger the `echo` method
                TxnField.application_args: [
                    do_optin_selector, 
                    Itob(Int(0))  # first item in assets array
                ],
                TxnField.assets: [InnerTxn.created_asset_id()],
                # Set fee to 0 so caller has to cover it
                TxnField.fee: Int(0),
            }
        ),
        InnerTxnBuilder.Next(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetFreeze,
                TxnField.freeze_asset: InnerTxn.created_asset_id(),
                TxnField.freeze_asset_frozen: Int(0),
                TxnField.freeze_asset_account: dump_address,
            }
        ),
        InnerTxnBuilder.Submit(),
        Int(1),
    )

unfreeze_nft_selector = MethodSignature(
    "unfreeze_nft(asset)void"
)
@Subroutine(TealType.uint64)
def unfreeze_nft():
    asset_id = Txn.assets[Btoi(Txn.application_args[1])]
    dump_address = Sha512_256(
        Concat(Bytes("appID"), Itob(App.globalGet(DUMP_APP_ID)))
    )
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetFreeze,
                TxnField.freeze_asset: asset_id,
                TxnField.freeze_asset_frozen: Int(0),
                TxnField.freeze_asset_account: Txn.sender(),
            }
        ),
        InnerTxnBuilder.Submit(),
        Int(1),
    )

swap_nft_to_fungible_selector = MethodSignature(
    "swap_nft_to_fungible(asset)uint64"
)
@Subroutine(TealType.uint64)
def swap_nft_to_fungible():
    transfer_tx = Gtxn[1]
    asset_id = Txn.assets[Btoi(Txn.application_args[1])]
    # ensure we are swapping an NFT fully
    asset_supply = AssetParam.total(transfer_tx.xfer_asset()).value()
    # ensure the NFT was minted by the contract
    asset_minter = AssetParam.creator(transfer_tx.xfer_asset())
    valid_swap = Assert(
        And(
            # no funny stuff
            Txn.rekey_to() == Global.zero_address(),
            Txn.close_remainder_to() == Global.zero_address(),
            Txn.application_args.length() == Int(2),
            Global.group_size() == Int(3),
            asset_id == transfer_tx.xfer_asset(),
            # not working?
            asset_minter.value() == Global.current_application_address()
        ))

    return Seq(
        asset_minter,
        valid_swap,
        ensure_opted_in(asset_id),
        # clawback all the asset and exposes InnerTxn.asset_amount() to mint some climatecoins
        # clawback_asset(asset_id, Txn.sender()),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: App.globalGet(CLIMATECOIN_ASA_ID),
                TxnField.asset_amount: transfer_tx.asset_amount(),
                TxnField.asset_receiver: Txn.sender(),
            }
        ),
        InnerTxnBuilder.Submit(),
        Int(1)
    )

burn_parameters_selector = MethodSignature(
    "burn_parameters()uint64"
)
@Subroutine(TealType.uint64)
def burn_parameters():
    return Seq(
        Log(Concat(return_prefix, Itob(Int(1)))),
        Int(1)
    )

burn_climatecoins_selector = MethodSignature(
    "burn_climatecoins()uint64"
)
@Subroutine(TealType.uint64)
def burn_climatecoins():
    transfer_tx = Gtxn[0]
    burn_parameters_txn = Gtxn[1]
    valid_burn = Assert(
        And(
            Txn.rekey_to() == Global.zero_address(),
            Txn.close_remainder_to() == Global.zero_address(),
            # No params, we send all the asa_ids in the foreign_assets
            Txn.application_args.length() == Int(1),
            Global.group_size() == Int(3),
            # Len(App.globalGet(DUMP_APP_ID)) != Int(0)
        ))

    dump_address = Sha512_256(
        Concat(Bytes("appID"), Itob(App.globalGet(DUMP_APP_ID)))
    )

    coins_to_burn = transfer_tx.asset_amount()

    total_co2_burned = ScratchVar(TealType.uint64)
    amount_to_burn = ScratchVar(TealType.uint64)
    i = ScratchVar(TealType.uint64)

    return Seq(
        valid_burn,
        # ensure_opted_in(asset_id),
        total_co2_burned.store(Int(0)),
        For(i.store(Int(0)), i.load() < burn_parameters_txn.assets.length(), i.store(Add(i.load(), Int(1)))).Do(
            Seq(
                # assert the nft was created by the contract
                # Assert(Global.current_application_address() == AssetParam.creator(burn_parameters_txn.assets[i.load()])),
                InnerTxnBuilder.Begin(),
                app_nft_balance := AssetHolding.balance(Global.current_application_address(), burn_parameters_txn.assets[i.load()]),
                # get the minimum between the assetHoldings and the amountToBurn
                amount_to_burn.store(min(app_nft_balance.value(), Minus(coins_to_burn, total_co2_burned.load()))),
                # store it in the scratchVar
                total_co2_burned.store(Add(total_co2_burned.load(), amount_to_burn.load())),
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.AssetTransfer,
                        TxnField.xfer_asset: burn_parameters_txn.assets[i.load()],
                        TxnField.asset_amount: amount_to_burn.load(),
                        TxnField.asset_receiver: dump_address,
                    }
                ),
                InnerTxnBuilder.Submit(),
            )
        ),
        Assert(Eq(coins_to_burn, total_co2_burned.load())),
        # log the total before we update the global value
        Log(Concat(return_prefix, Itob(total_co2_burned.load()))),
        # update the global value
        App.globalPut(TOTAL_COINS_BURNED, Add(App.globalGet(TOTAL_COINS_BURNED), coins_to_burn)),
        Int(1)
    )

mint_climatecoin_selector = MethodSignature(
    "mint_climatecoin()uint64"
)
@Subroutine(TealType.uint64)
def mint_climatecoin():
    can_mint = Assert(App.globalGet(CLIMATECOIN_ASA_ID) == Int(0))
    return Seq(
        can_mint,
        InnerTxnBuilder.Begin(),
        # This method accepts a dictionary of TxnField to value so all fields may be set 
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_name: Bytes("Climatecoin"),
            TxnField.config_asset_unit_name: Bytes("CC"),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.zero_address(),
            TxnField.config_asset_freeze: Global.zero_address(),
            TxnField.config_asset_total: Int(150_000_000_000),
            TxnField.config_asset_decimals: Int(0),
            TxnField.fee: Int(0),
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

set_dump_selector = MethodSignature(
    "set_dump(uint64)address"
)
@Subroutine(TealType.uint64)
def set_dump():
    return Seq(
        App.globalPut(DUMP_APP_ID, Btoi(Txn.application_args[1])),
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
            App.globalPut(DUMP_APP_ID, Int(0)),
            App.globalPut(TOTAL_COINS_BURNED, Int(0)),
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
        [And(Txn.application_args[0] == set_dump_selector, from_creator), set_dump()],
        [And(Txn.application_args[0] == burn_parameters_selector), burn_parameters()],
        [And(Txn.application_args[0] == burn_climatecoins_selector), burn_climatecoins()],
        [Txn.application_args[0] == unfreeze_nft_selector, unfreeze_nft()],
        [Txn.application_args[0] == swap_nft_to_fungible_selector, swap_nft_to_fungible()],
    )

    return Cond(
        #  handle app creation
        [Txn.application_id() == Int(0), Return(initialize_vault())],
        #  disallow all to opt-in and close-out
        [Txn.on_completion() == OnComplete.OptIn, Reject()],
        [Txn.on_completion() == OnComplete.CloseOut, Reject()],
        #  allow creator to update and delete app
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.NoOp, Return(handle_noop)]
    )


def clear():
    return Return(
        Int(1)
    )


def get_approval():
    return compileTeal(contract(), mode=Mode.Application, version=6)


def get_clear():
    return compileTeal(clear(), mode=Mode.Application, version=6)


if __name__ == "__main__":
    print(get_approval())