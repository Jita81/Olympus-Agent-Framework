def test_merkle_stable(tmp_path):
    from olympus.merkle import directory_merkle_root

    (tmp_path / "a.txt").write_text("hello")
    r1 = directory_merkle_root(tmp_path)
    r2 = directory_merkle_root(tmp_path)
    assert r1 == r2
    (tmp_path / "a.txt").write_text("hello2")
    r3 = directory_merkle_root(tmp_path)
    assert r3 != r1
