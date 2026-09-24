import conciliador


def test_pacote_importa_e_tem_versao():
    assert conciliador.__version__ == "0.1.0"
