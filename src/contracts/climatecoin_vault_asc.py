# VRF contract example
# https://github.com/ori-shem-tov/vrf-oracle/blob/vrf-teal5/pyteal/teal5.py

from pyteal import *
import base64

from src.pyteal_utils import ensure_opted_in, min, div_ceil
from src.utils import get_burn_contracts
from src.contracts.climatecoin_dump_asc import do_optin_selector
from src.contracts.climatecoin_burn_asc import USER_ADDRESS_KEY

TEAL_VERSION = 6

return_prefix = Bytes("base16", "0x151f7c75")  # Literally hash('return')[:4]

# Global Vars
ORACLE_ADDRESS = Bytes('oracle_address')
CLIMATECOIN_ASA_ID = Bytes('climatecoin_asa_id')
MINT_FEE = Bytes('nft_mint_fee')
TOTAL_COINS_BURNED = Bytes('total_coins_burned')
DUMP_APP_ID = Bytes('dump_app_id')

# Nft Vars
CO2_NFT_ASSET_UNIT_NAME = Bytes("CO2")
COMPENSATION_NFT_ASSET_UNIT_NAME = Bytes("BUYCO2")

# Contracts
burn_app, burn_clear = get_burn_contracts()
BURN_APP_TEAL = Bytes('base64', burn_app)
BURN_CLEAR_TEAL = Bytes('base64', burn_clear)


@Subroutine(TealType.none)
def mint_climate_nft(normalize_fee, note):
    dump_address = Sha512_256(
        Concat(Bytes("appID"), Itob(App.globalGet(DUMP_APP_ID))))

    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_name: Bytes("CO2TONNE@ARC69"),
                TxnField.config_asset_unit_name: CO2_NFT_ASSET_UNIT_NAME,
                TxnField.config_asset_total: normalize_fee,
                TxnField.config_asset_decimals: Int(0),
                TxnField.config_asset_manager: Global.current_application_address(),
                TxnField.config_asset_reserve: dump_address,
                TxnField.config_asset_freeze: Global.current_application_address(),
                # TODO: do we need a clawback for this??
                TxnField.config_asset_clawback: Global.current_application_address(),
                TxnField.config_asset_default_frozen: Int(1),
                TxnField.note: note
            }
        ),
        InnerTxnBuilder.Submit(),
        Log(Concat(return_prefix, Itob(InnerTxn.created_asset_id()))),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(DUMP_APP_ID),
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
    )


mint_developer_nft_selector = MethodSignature(
    "mint_developer_nft(uint64,application,account)uint64"
)


@Subroutine(TealType.uint64)
def mint_developer_nft():
    #
    multiplier = Int(1000)
    nft_total_supply = Btoi(Txn.application_args[1])
    amount = Mul(nft_total_supply, multiplier)

    total = Mul(Div(amount, Int(100)), Minus(Int(100), App.globalGet(MINT_FEE)))
    fee = Mul(Div(amount, Int(100)), App.globalGet(MINT_FEE))

    normalize_total = Div(total, multiplier)
    normalize_fee = div_ceil(fee, multiplier)

    return Seq(
        If(App.globalGet(MINT_FEE) != Int(0))
        .Then(mint_climate_nft(normalize_fee, Txn.note())),
        mint_climate_nft(normalize_total, Txn.note()),
        Int(1),
    )


mint_compensation_nft_selector = MethodSignature(
    "mint_compensation_nft()uint64"
)


@Subroutine(TealType.uint64)
def mint_compensation_nft():
    return Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_name: Bytes("CO2_COMPENSATION@ARC69"),
                TxnField.config_asset_unit_name: COMPENSATION_NFT_ASSET_UNIT_NAME,
                TxnField.config_asset_total: Int(1),
                TxnField.config_asset_decimals: Int(0),
                TxnField.config_asset_manager: Global.current_application_address(),
                # TODO: who is the reserve of this?
                TxnField.config_asset_reserve: Global.current_application_address(),
                TxnField.config_asset_freeze: Global.current_application_address(),
                TxnField.config_asset_clawback: Global.current_application_address(),
                TxnField.config_asset_default_frozen: Int(0),
                TxnField.note: Txn.note()
            }
        ),
        InnerTxnBuilder.Submit(),
        Log(Concat(return_prefix, Itob(InnerTxn.created_asset_id()))),
        Int(1)
    )


unfreeze_nft_selector = MethodSignature(
    "unfreeze_nft(asset)void"
)


@Subroutine(TealType.uint64)
def unfreeze_nft():
    asset_id = Txn.assets[Btoi(Txn.application_args[1])]
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
    unfreeze_txn = Gtxn[0]
    transfer_tx = Gtxn[1]
    asset_id = Txn.assets[Btoi(Txn.application_args[1])]
    # ensure we are swapping an NFT fully
    asset_supply = AssetParam.total(transfer_tx.xfer_asset())
    # ensure the NFT was minted by the contract
    asset_minter = AssetParam.creator(transfer_tx.xfer_asset())
    # ensure the type of NFT
    asset_unit_name = AssetParam.unitName(transfer_tx.xfer_asset())
    valid_swap = Assert(
        And(
            # no funny stuff
            Txn.rekey_to() == Global.zero_address(),
            Txn.close_remainder_to() == Global.zero_address(),
            Txn.application_args.length() == Int(2),
            Global.group_size() == Int(3),
            # is the contract the minter of the NFT
            asset_minter.value() == Global.current_application_address(),
            # make sure were using the same asset
            transfer_tx.xfer_asset() == asset_id,
            asset_unit_name.value() == CO2_NFT_ASSET_UNIT_NAME,  # is it the correct NFT
            transfer_tx.asset_receiver() == Global.current_application_address(),  # are we receiving the asset fully
            transfer_tx.asset_amount() == asset_supply.value()  # are we sending all the supply
        ))

    return Seq(
        asset_minter,
        asset_supply,
        asset_unit_name,
        valid_swap,
        ensure_opted_in(asset_id),
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
    valid_transfer_txn = Assert(
        And(
            # did the user send us climatecoins?
            transfer_tx.xfer_asset() == App.globalGet(CLIMATECOIN_ASA_ID),
            # are we the receivers of the transfer?
            transfer_tx.asset_receiver() == Global.current_application_address(),
            # is the txn of type Axfer
            transfer_tx.type_enum() == TxnType.AssetTransfer
        )
    )
    burn_parameters_txn = Gtxn[2]
    valid_burn_parameters_txn = Assert(
        And(
            # does the txn call the correct method
            burn_parameters_txn.application_args[0] == burn_parameters_selector,
            # did they call the selector in our contract?
            # burn_parameters_txn.asset_receiver() == Global.current_application_address()
            # TODO: Preguntar a fer sobre este assert
        )
    )
    valid_burn = Assert(
        And(
            # no funky stuff
            Txn.rekey_to() == Global.zero_address(),
            Txn.close_remainder_to() == Global.zero_address(),
            # No params, we send all the asa_ids in the foreign_assets
            Txn.application_args.length() == Int(1),
            Global.group_size() == Int(4),
            # Len(App.globalGet(DUMP_APP_ID)) != Int(0)
        )
    )

    coins_to_burn = transfer_tx.asset_amount()

    burn_contract_id = ScratchVar(TealType.uint64)
    total_co2_burned = ScratchVar(TealType.uint64)
    amount_to_burn = ScratchVar(TealType.uint64)
    i = ScratchVar(TealType.uint64)

    return Seq(
        valid_transfer_txn,
        valid_burn_parameters_txn,
        valid_burn,
        # ensure_opted_in(asset_id),
        total_co2_burned.store(Int(0)),

        dump_app_add := AppParam.address(App.globalGet(DUMP_APP_ID)),

        # Deploy the burn contract
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.fee: Int(0),
                TxnField.approval_program: BURN_APP_TEAL,
                TxnField.clear_state_program: BURN_CLEAR_TEAL,
                TxnField.on_completion: Int(0),
                TxnField.global_num_uints: Int(1),
                TxnField.global_num_byte_slices: Int(2),
                TxnField.local_num_uints: Int(0),
                TxnField.local_num_byte_slices: Int(0),
                TxnField.accounts: [Txn.sender(), dump_app_add.value()]
            }
        ),
        InnerTxnBuilder.Submit(),

        burn_contract_id.store(InnerTxn.created_application_id()),
        Log(Concat(return_prefix, Itob(InnerTxn.created_application_id()))),
        burn_app_add := AppParam.address(InnerTxn.created_application_id()),

        # Send algos to new contract to be able to receive assets
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.Payment,
                TxnField.amount: Add(Int(100000), Mul(Int(100000), Txn.assets.length())),
                TxnField.receiver: burn_app_add.value(),
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Next(),
        # Optin from the burn contract to climatecoin
        InnerTxnBuilder.MethodCall(
            app_id=burn_contract_id.load(),
            method_signature="opt_in(asset)void",
            args=[
                transfer_tx.xfer_asset()
            ],
            extra_fields={
                TxnField.fee: Int(0)
            }
        ),
        InnerTxnBuilder.Next(),
        # Transfer of climatecoins to burn contract
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: transfer_tx.xfer_asset(),
                TxnField.asset_amount: transfer_tx.asset_amount(),
                TxnField.asset_receiver: burn_app_add.value(),
            }
        ),
        InnerTxnBuilder.Submit(),

        # Iterate CO2TONNE nfts
        For(i.store(Int(0)), i.load() < burn_parameters_txn.assets.length(), i.store(Add(i.load(), Int(1)))).Do(
            Seq(
                asset_unit_name := AssetParam.unitName(burn_parameters_txn.assets[i.load()]),
                asset_creator := AssetParam.creator(burn_parameters_txn.assets[i.load()]),

                # assert the nft was created by the contract
                Assert(
                    And(
                        asset_creator.value() == Global.current_application_address(),
                        asset_unit_name.value() == CO2_NFT_ASSET_UNIT_NAME
                    )
                ),

                InnerTxnBuilder.Begin(),
                app_nft_balance := AssetHolding.balance(Global.current_application_address(),
                                                        burn_parameters_txn.assets[i.load()]),
                # get the minimum between the assetHoldings and the amountToBurn
                amount_to_burn.store(min(app_nft_balance.value(), Minus(coins_to_burn, total_co2_burned.load()))),
                # store it in the scratchVar
                total_co2_burned.store(Add(total_co2_burned.load(), amount_to_burn.load())),

                # Optin burn app to the nft
                InnerTxnBuilder.MethodCall(
                    app_id=burn_contract_id.load(),
                    method_signature="opt_in(asset)void",
                    args=[
                        burn_parameters_txn.assets[i.load()]
                    ],
                    extra_fields={
                        TxnField.fee: Int(0)
                    }
                ),
                InnerTxnBuilder.Next(),
                # Unfreeze the nft on the burn app
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.AssetFreeze,
                        TxnField.freeze_asset: burn_parameters_txn.assets[i.load()],
                        TxnField.freeze_asset_frozen: Int(0),
                        TxnField.freeze_asset_account: burn_app_add.value(),
                    }
                ),
                InnerTxnBuilder.Next(),
                # Send the nft to the burn app
                InnerTxnBuilder.SetFields(
                    {
                        TxnField.type_enum: TxnType.AssetTransfer,
                        TxnField.xfer_asset: burn_parameters_txn.assets[i.load()],
                        TxnField.asset_amount: amount_to_burn.load(),
                        TxnField.asset_receiver: burn_app_add.value(),
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


approve_burn_selector = MethodSignature(
    "approve_burn(application,asset)uint64"
)


@Subroutine(TealType.uint64)
def approve_burn():
    burn_app_id = Txn.applications[Btoi(Txn.application_args[1])]
    compensation_nft_id = Txn.assets[Btoi(Txn.application_args[2])]
    compensation_nft_creator = AssetParam.creator(compensation_nft_id)
    compensation_nft_name = AssetParam.unitName(compensation_nft_id)
    valid_asset = Seq(
        compensation_nft_creator,
        compensation_nft_name,
        Assert(And(
            compensation_nft_creator.value() == Global.current_application_address(),
            compensation_nft_name.value() == COMPENSATION_NFT_ASSET_UNIT_NAME
        ))
    )
    i = ScratchVar(TealType.uint64)
    return Seq(
        valid_asset,
        burn_app_add := AppParam.address(App.globalGet(DUMP_APP_ID)),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.MethodCall(
            app_id=burn_app_id,
            method_signature="approve()void",
            args=[],
            extra_fields={
                TxnField.fee: Int(0),
                TxnField.accounts: [burn_app_add.value()]
            }
        ),
        # TODO: Chore con https://github.com/algorand/pyteal/pull/384
        For(i.store(Int(0)), i.load() < Txn.assets.length(), i.store(Add(i.load(), Int(1)))).Do(
            InnerTxnBuilder.SetField(TxnField.assets, [Txn.assets[i.load()]])
        ),
        InnerTxnBuilder.Next(),
        user_address := App.globalGetEx(burn_app_id, USER_ADDRESS_KEY),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.AssetTransfer,
                TxnField.xfer_asset: compensation_nft_id,
                TxnField.asset_amount: Int(1),
                TxnField.asset_sender: Global.current_application_address(),
                TxnField.asset_receiver: user_address.value(),
            }
        ),
        InnerTxnBuilder.Submit(),
        Int(1)
    )


reject_burn_selector = MethodSignature(
    "reject_burn(application)uint64"
)


@Subroutine(TealType.uint64)
def reject_burn():
    burn_app_id = Txn.applications[Btoi(Txn.application_args[1])]
    i = ScratchVar(TealType.uint64)
    return Seq(
        burn_app_add := AppParam.address(App.globalGet(DUMP_APP_ID)),
        user_address := App.globalGetEx(burn_app_id, USER_ADDRESS_KEY),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.MethodCall(
            app_id=burn_app_id,
            method_signature="reject()void",
            args=[],
            extra_fields={
                TxnField.fee: Int(0),
                TxnField.accounts: [burn_app_add.value(), user_address.value()]
            }
        ),
        # TODO: Chore con https://github.com/algorand/pyteal/pull/384
        For(i.store(Int(0)), i.load() < Txn.assets.length(), i.store(Add(i.load(), Int(1)))).Do(
            InnerTxnBuilder.SetField(TxnField.assets, [Txn.assets[i.load()]])
        ),
        InnerTxnBuilder.Submit(),
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

        # Optin of Climatecoin on the dump account
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields(
            {
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: App.globalGet(DUMP_APP_ID),
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
    return Seq(
        move_asset(asset_id, from_acct, to_acct, amount),
        Int(1)
    )


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
        # actions
        [And(Txn.application_args[0] == mint_developer_nft_selector, from_creator), mint_developer_nft()],
        [Txn.application_args[0] == unfreeze_nft_selector, unfreeze_nft()],
        [And(Txn.application_args[0] == move_selector, from_creator), move()],
        [Txn.application_args[0] == swap_nft_to_fungible_selector, swap_nft_to_fungible()],
        [And(Txn.application_args[0] == burn_parameters_selector, from_creator), burn_parameters()],
        [And(Txn.application_args[0] == burn_climatecoins_selector), burn_climatecoins()],
        [And(Txn.application_args[0] == approve_burn_selector, from_creator), approve_burn()],
        [And(Txn.application_args[0] == reject_burn_selector, from_creator), reject_burn()],
        [And(Txn.application_args[0] == mint_compensation_nft_selector, from_creator), mint_compensation_nft()],
        # setters
        [And(Txn.application_args[0] == set_fee_selector, from_creator), set_fee()],
        [And(Txn.application_args[0] == set_dump_selector, from_creator), set_dump()],
        # config
        [And(Txn.application_args[0] == mint_climatecoin_selector, from_creator), mint_climatecoin()],
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
