# VRF contract example
# https://github.com/ori-shem-tov/vrf-oracle/blob/vrf-teal5/pyteal/teal5.py

from pyteal import *

from src.utils import aoptin, ensure_opted_in

TEAL_VERSION = 6

# Schema
ORACLE_GLOBAL_BYTES = 1
ORACLE_GLOBAL_INTS = 1
ORACLE_LOCAL_BYTES = 0
ORACLE_LOCAL_INTS = 0

# Global Vars
GLOBAL_NFT_MINTER_ADDRESS=Bytes('nft_minter_address')
GLOBAL_CLIMATECOIN_ASA_ID=Bytes('climatecoin_asa_id')



swap_nft_to_fungible_selector = MethodSignature(
    "swap_nft_to_fungible(asset,uint64)void"
)

@Subroutine(TealType.uint64)
def swap_nft_to_fungible():
    transfer_txn = Gtxn[0]
    oracle_txn = Gtxn[1]

    valid_swap = Seq([
        Assert(Global.group_size() == Int(3)),
        #  this application serves as the escrow for the fee
        # Assert(payment_txn.receiver() == Global.current_application_address()),
        # Assert(payment_txn.type_enum() == TxnType.Payment),
        # Assert(payment_txn.amount() == App.globalGet(GLOBAL_SERVICE_FEE)),
    ])

    return Seq([
        valid_swap,
        ensure_opted_in(Txn.application_args[1]),
        Int(1)
    ])

def contract():

    def initialize_vault():
        return Seq([
            App.globalPut(GLOBAL_NFT_MINTER_ADDRESS, Itob(0)),
            App.globalPut(GLOBAL_CLIMATECOIN_ASA_ID, Int(0)),
            Int(1)
        ])

    
    nft_optin = Seq([
        aoptin(Global.current_application_address, Txn.application_args[1])
    ])

    #  the fee payment transactions is always 1 transaction before the application call
    payment_txn = Gtxn[Txn.group_index() - Int(1)]
    mint_climatecoin = Seq([
        InnerTxnBuilder.Begin(),    
        # This method accepts a dictionary of TxnField to value so all fields may be set 
        InnerTxnBuilder.SetFields({ 
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_name: Txn.application_args[1],
            TxnField.config_asset_unit_name: Txn.application_args[2],
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_reserve: Global.current_application_address(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_total: Btoi(Txn.application_args[3]),
            TxnField.config_asset_decimals: Int(0),
        }),

        # Submit the transaction we just built
        InnerTxnBuilder.Submit(),   
        Int(1)
    ]) 

    set_minter_address = Seq([
        App.globalPut(GLOBAL_NFT_MINTER_ADDRESS, Addr(Txn.application_args[1])),
        Int(1)
    ])

    handle_noop = Cond(
        [Txn.application_args[0] == Bytes('nft_optin'), Return(nft_optin)],
        [Txn.application_args[0] == Bytes('mint_climatecoin'), Return(mint_climatecoin)],
        [Txn.application_args[0] == Bytes('set_minter_address'), Return(set_minter_address)],
        [Txn.application_args[0] == Bytes('swap_nft_for_coins'), Return(swap_nft_to_fungible())],
    )

    program = Cond(
        #  handle app creation
        [Txn.application_id() == Int(0), initialize_vault()],
        #  allow all to opt-in and close-out
        [Txn.on_completion() == OnComplete.OptIn, Approve()],
        [Txn.on_completion() == OnComplete.CloseOut, Approve()],
        #  allow creator to update and delete app
        [Txn.on_completion() == OnComplete.DeleteApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.UpdateApplication, Return(Txn.sender() == Global.creator_address())],
        [Txn.on_completion() == OnComplete.NoOp, handle_noop]
    )

    return compileTeal(program, Mode.Application, version=TEAL_VERSION)

def contract_clear():
    return compileTeal(Approve(), Mode.Application, version=TEAL_VERSION)

if __name__ == '__main__':
    filename = 'climatecoin_vault.teal'
    with open(filename, 'w') as f:
        compiled = contract()
        f.write(compiled)
        print(f'compiled {filename}')

    filename = 'climatecoin_vault_clear.teal'
    with open(filename, 'w') as f:
        compiled = contract_clear()
        f.write(compiled)
        print(f'compiled {filename}')