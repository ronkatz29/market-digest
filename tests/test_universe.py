from market_digest.universe import Company, load_universe


def test_loads_bundled_sp500_list():
    companies = load_universe()
    assert len(companies) >= 500
    assert all(c.ticker and c.name and c.sector for c in companies)
    assert len({c.ticker for c in companies}) == len(companies)


def test_loads_custom_csv(tmp_path):
    path = tmp_path / "u.csv"
    path.write_text("ticker,name,sector\nAAPL,Apple Inc.,Information Technology\n")
    assert load_universe(path) == [Company("AAPL", "Apple Inc.", "Information Technology")]
