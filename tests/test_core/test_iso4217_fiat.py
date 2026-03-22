"""core.iso4217_fiat: фильтр криптовалют для autocomplete фиата."""
from core.iso4217_fiat import iso4217_active_fiat_only


def test_iso4217_active_fiat_only_drops_crypto_tickers():
    s = {"USD", "AAVE", "RUB", "ADA"}
    assert iso4217_active_fiat_only(s) == {"USD", "RUB"}
