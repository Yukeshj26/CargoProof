# CargoProof Algorand TestNet escrow

This is a PyTeal reference escrow for an Algorand Standard Asset (ASA), defaulting to GoPlausible's documented Algorand TestNet USDC asset ID `10458941`. It is separate from x402 provider procurement and Base Sepolia customer payment verification.

## Important operational requirements
- Install `py-algorand-sdk`, `pyteal`, and `python-dotenv` in the backend environment.
- Put an operator/verifier TestNet mnemonic in `backend/.env` as `ALGORAND_VERIFIER_MNEMONIC`. Never put it in Vite/frontend variables or commit it.
- The deployer is also the verifier and depositor in this reference CLI. The beneficiary must already be opted into the ASA.
- Fund the application account with the required TestNet ASA after running `optin`.
- The contract is a hackathon reference, not audited financial software. Test only with worthless TestNet funds.

## Commands
From `CargoProof-AI` root, after installing backend dependencies:

```powershell
python contracts/algorand/scripts/escrow_cli.py deploy --beneficiary YOUR_BENEFICIARY_ALGORAND_ADDRESS
python contracts/algorand/scripts/escrow_cli.py optin --app-id APP_ID
python contracts/algorand/scripts/escrow_cli.py fund --app-id APP_ID --amount 1000000
python contracts/algorand/scripts/escrow_cli.py evidence --app-id APP_ID --sha256 64_CHARACTER_SHA256 --amount 1000000
python contracts/algorand/scripts/escrow_cli.py release --app-id APP_ID --beneficiary BENEFICIARY_ADDRESS
python contracts/algorand/scripts/escrow_cli.py status --app-id APP_ID
```

The ASA amount is in base units (USDC has six decimals). `hold` can be called by the verifier. `refund` is available to the depositor after expiry while the application is pending or held. Each application call that creates an inner transaction is submitted with a fee budget of 2,000 microAlgos.

The CLI prints transaction IDs and confirmed rounds. It does not silently mark the database as released; backend integration must independently query confirmed application state before reflecting settlement.
