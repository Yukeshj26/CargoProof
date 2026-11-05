"""CargoProof TestNet ASA escrow reference contract (PyTeal).
Audit before any production use. App account must be opted into the configured ASA.
"""
from pyteal import *
PENDING, VERIFIED, RELEASED, HELD, REFUNDED = Int(0), Int(1), Int(2), Int(3), Int(4)
ASSET, BENEFICIARY, VERIFIER, DEPOSITOR = Bytes('asset'), Bytes('beneficiary'), Bytes('verifier'), Bytes('depositor')
STATUS, HASH, AMOUNT, EXPIRY = Bytes('status'), Bytes('evidence_hash'), Bytes('amount'), Bytes('expiry')

def approval():
    init = Seq([
        Assert(Txn.application_args.length() == Int(6)),
        Assert(Txn.application_args[0] == Bytes('init')),
        Assert(Btoi(Txn.application_args[1]) > Int(0)),
        Assert(Len(Txn.application_args[2]) == Int(32)),
        Assert(Len(Txn.application_args[3]) == Int(32)),
        Assert(Len(Txn.application_args[4]) == Int(32)),
        Assert(Btoi(Txn.application_args[5]) > Global.latest_timestamp()),
        App.globalPut(ASSET, Btoi(Txn.application_args[1])),
        App.globalPut(BENEFICIARY, Txn.application_args[2]),
        App.globalPut(VERIFIER, Txn.application_args[3]),
        App.globalPut(DEPOSITOR, Txn.application_args[4]),
        App.globalPut(AMOUNT, Int(0)),
        App.globalPut(EXPIRY, Btoi(Txn.application_args[5])),
        App.globalPut(STATUS, PENDING),
        App.globalPut(HASH, Bytes('')),
        Approve(),
    ])
    optin = Seq([
        Assert(Txn.sender() == App.globalGet(VERIFIER)),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({TxnField.type_enum: TxnType.AssetTransfer, TxnField.xfer_asset: App.globalGet(ASSET), TxnField.asset_amount: Int(0), TxnField.asset_receiver: Global.current_application_address(), TxnField.fee: Int(0)}),
        InnerTxnBuilder.Submit(), Approve(),
    ])
    set_terms = Seq([
        Assert(Txn.sender() == App.globalGet(VERIFIER)),
        Assert(App.globalGet(STATUS) == PENDING),
        Assert(Global.latest_timestamp() <= App.globalGet(EXPIRY)),
        Assert(Txn.application_args.length() == Int(3)),
        Assert(Len(Txn.application_args[1]) == Int(32)),
        Assert(Btoi(Txn.application_args[2]) > Int(0)),
        App.globalPut(HASH, Txn.application_args[1]),
        App.globalPut(AMOUNT, Btoi(Txn.application_args[2])),
        App.globalPut(STATUS, VERIFIED),
        Approve(),
    ])
    hold = Seq([Assert(Txn.sender() == App.globalGet(VERIFIER)), Assert(Or(App.globalGet(STATUS) == PENDING, App.globalGet(STATUS) == VERIFIED)), App.globalPut(STATUS, HELD), Approve()])
    release = Seq([
        Assert(Txn.sender() == App.globalGet(VERIFIER)), Assert(App.globalGet(STATUS) == VERIFIED),
        Assert(Global.latest_timestamp() <= App.globalGet(EXPIRY)),
        Assert(App.globalGet(AMOUNT) > Int(0)), Assert(Txn.accounts[1] == App.globalGet(BENEFICIARY)),
        Assert(Txn.assets[0] == App.globalGet(ASSET)),
        Assert(AssetHolding.balance(Global.current_application_address(), App.globalGet(ASSET)).hasValue()),
        Assert(AssetHolding.balance(Global.current_application_address(), App.globalGet(ASSET)).value() >= App.globalGet(AMOUNT)),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({TxnField.type_enum: TxnType.AssetTransfer, TxnField.xfer_asset: App.globalGet(ASSET), TxnField.asset_amount: App.globalGet(AMOUNT), TxnField.asset_receiver: App.globalGet(BENEFICIARY), TxnField.fee: Int(0)}),
        InnerTxnBuilder.Submit(), App.globalPut(AMOUNT, Int(0)), App.globalPut(STATUS, RELEASED), Approve(),
    ])
    refund = Seq([
        Assert(Txn.sender() == App.globalGet(DEPOSITOR)), Assert(Global.latest_timestamp() > App.globalGet(EXPIRY)),
        Assert(Or(App.globalGet(STATUS) == PENDING, App.globalGet(STATUS) == VERIFIED, App.globalGet(STATUS) == HELD)), Assert(Txn.assets[0] == App.globalGet(ASSET)),
        Assert(AssetHolding.balance(Global.current_application_address(), App.globalGet(ASSET)).hasValue()),
        Assert(AssetHolding.balance(Global.current_application_address(), App.globalGet(ASSET)).value() > Int(0)),
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({TxnField.type_enum: TxnType.AssetTransfer, TxnField.xfer_asset: App.globalGet(ASSET), TxnField.asset_amount: AssetHolding.balance(Global.current_application_address(), App.globalGet(ASSET)).value(), TxnField.asset_receiver: App.globalGet(DEPOSITOR), TxnField.fee: Int(0)}),
        InnerTxnBuilder.Submit(), App.globalPut(AMOUNT, Int(0)), App.globalPut(STATUS, REFUNDED), Approve(),
    ])
    return Seq([
        Assert(Txn.on_completion() == OnComplete.NoOp),
        Cond(
        [Txn.application_id() == Int(0), init],
        [Txn.application_args[0] == Bytes('optin'), optin],
        [Txn.application_args[0] == Bytes('evidence'), set_terms],
        [Txn.application_args[0] == Bytes('hold'), hold],
        [Txn.application_args[0] == Bytes('release'), release],
        [Txn.application_args[0] == Bytes('refund'), refund],
        ),
    ])

def clear(): return Return(Int(0))

if __name__ == '__main__':
    print(compileTeal(approval(), Mode.Application, version=8))
    print('---CLEAR---')
    print(compileTeal(clear(), Mode.Application, version=8))
