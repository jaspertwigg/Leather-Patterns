from app.naming import clean_title


def test_strips_extension_underscores_and_copy_suffix():
    assert clean_title("Classic_Trifold_-_Copy.lcc") == "Classic Trifold"


def test_strips_a_leading_upload_hash_prefix():
    assert clean_title("3a28aeb7-Horizontal_Card_Holder.lcc") == "Horizontal Card Holder"


def test_leaves_an_already_nice_name_alone():
    assert clean_title("Already Nice Name.pdf") == "Already Nice Name"
