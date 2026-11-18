class Keelway < Formula
  include Language::Python::Virtualenv

  desc "Customer-managed governance and audit platform for AI-powered software change"
  homepage "https://keelway.dev"
  url "https://github.com/creova-gif/keelway/releases/download/v1.1.0/keelway-1.1.0.tar.gz"
  sha256 "87f2ff7e0e2ad85aa62b1b3eadbdac916bcfd412bc6b60db642eed2d17672526"
  license "PROPRIETARY"
  version "1.1.0"

  depends_on "python@3.13"

    resource "aiosqlite" do
      url "https://files.pythonhosted.org/packages/00/b7/e3bf5133d697a08128598c8d0abc5e16377b51465a33756de24fa7dee953/aiosqlite-0.22.1-py3-none-any.whl"
      sha256 "21c002eb13823fad740196c5a2e9d8e62f6243bd9e7e4a1f87fb5e44ecb4fceb"
    end

    resource "annotated_doc" do
      url "https://files.pythonhosted.org/packages/cd/f5/3dd85d583e55be76cd02b1fc9bbec771b12d63124b01661d9535ccf8721f/annotated_doc-0.0.6-py3-none-any.whl"
      sha256 "361ca0950cc7082f53fa69e9328409f40a62c61e57e0a47e1825a08078a58a53"
    end

    resource "annotated_types" do
      url "https://files.pythonhosted.org/packages/99/91/8acff4f5e50511b911bbccb72b8628a49c68ce14148cd9f6431094859a90/annotated_types-0.8.0-py3-none-any.whl"
      sha256 "f072f4d804ea359e4eaf198b1af7a8b0943881a87f31bb764f8bf219bb9419e0"
    end

    resource "anyio" do
      url "https://files.pythonhosted.org/packages/a9/16/7757fb84c819accc7d7e9af5291b261e4abb8627ee040f99e7d35ef2457a/anyio-4.16.0-py3-none-any.whl"
      sha256 "c66ae634e0b8228396b801741beb3294326d4b6102f7bba4041c0dfb58c29026"
    end

    resource "certifi" do
      url "https://files.pythonhosted.org/packages/32/d1/a3652fe2c19134d0d15922177821d863cbd7e842d53a21bbe7e8e3a1b5ac/certifi-2026.10.23-py3-none-any.whl"
      sha256 "e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1"
    end

    resource "click" do
      url "https://files.pythonhosted.org/packages/31/7d/164b7ffc8624fe9efb4221bf9af485d5c1e41b9ae118045d2b6dc5457d8b/click-8.5.1-py3-none-any.whl"
      sha256 "8bb5376d2006950386f8c6427613334a2acadc5f559cb80e638d00b4df957e37"
    end

    resource "fastapi" do
      url "https://files.pythonhosted.org/packages/58/ef/bf79bc47e914dfabc56657bb6a2d33340b1faa5a514b0b92e842aa088d1e/fastapi-0.163.2-py3-none-any.whl"
      sha256 "825a8fdd18d7bfcb1b86735e9805c59b7400d55c4060d3df5331b62ae452f004"
    end

    resource "h11" do
      url "https://files.pythonhosted.org/packages/04/4b/29cac41a4d98d144bf5f6d33995617b185d14b22401f75ca86f384e87ff1/h11-0.16.0-py3-none-any.whl"
      sha256 "63cf8bbe7522de3bf65932fda1d9c2772064ffb3dae62d55932da54b31cb6c86"
    end

    resource "httpcore" do
      url "https://files.pythonhosted.org/packages/7e/f5/f66802a942d491edb555dd61e3a9961140fd64c90bce1eafd741609d334d/httpcore-1.0.9-py3-none-any.whl"
      sha256 "2d400746a40668fc9dec9810239072b40b4484b640a8c38fd654a024c7a1bf55"
    end

    resource "httpx" do
      url "https://files.pythonhosted.org/packages/2a/39/e50c7c3a983047577ee07d2a9e53faf5a69493943ec3f6a384bdc792deb2/httpx-0.28.1-py3-none-any.whl"
      sha256 "d909fcccc110f8c7faf814ca82a9a4d816bc5a6dbfea25d6591d6985b8ba59ad"
    end

    resource "idna" do
      url "https://files.pythonhosted.org/packages/58/a2/bb081bab032533a855d44de1d56f8e8426114ff1ba5d1f07a438a0a654f8/idna-3.20-py3-none-any.whl"
      sha256 "ab7ae7122974553370f0bdb919e1a960b2cd1bc1ef0276416d896db81c14582c"
    end

    resource "opentelemetry_api" do
      url "https://files.pythonhosted.org/packages/a9/2d/610db864d7513158cebb8f36cc88e67e73bd6c7aa1905ef18d89e1281c81/opentelemetry_api-1.45.2-py3-none-any.whl"
      sha256 "2cbd737377e710ee740d261c94e93fa0f08e6d037c18f17513cc0a2d94479a34"
    end

    resource "pycparser" do
      url "https://files.pythonhosted.org/packages/b6/ae/315bbeee126a769cbde43cf4908acb4b40408d8bf8bbf334dd7368d8dadf/pycparser-3.12-py3-none-any.whl"
      sha256 "a076f3f489b39b43ed13563a1dafe42447445bec2e294154ec5c57fcdda4c85e"
    end

    resource "pydantic" do
      url "https://files.pythonhosted.org/packages/72/b8/b864503789ef5c58597d2a7b4adbee62c26440ab1e682581fc6838df8947/pydantic-2.14.3-py3-none-any.whl"
      sha256 "3f7b347782ab7e4cf4c798496ae3a82787d9f21ec12676a9c564355eeef8daa8"
    end

    resource "pydantic_settings" do
      url "https://files.pythonhosted.org/packages/4c/26/3e68379ca313b6aa58e11fbd8b28d5c6f1b9f4428d70222ba021a76797ec/pydantic_settings-2.16.3-py3-none-any.whl"
      sha256 "d1db16a2d34006323a1b42c0640898da58adfbad7ec30baaa9e2b18aafc08999"
    end

    resource "python_dotenv" do
      url "https://files.pythonhosted.org/packages/60/d1/38f3a3405989a89ac18390803e70c6ad7c7760da4f9b83cbeca0c44a0c72/python_dotenv-1.2.4-py3-none-any.whl"
      sha256 "42269a8a5b3fd54ffa6f3d84b18abed50064717576b4ecf03dc4a55d8aa04fdc"
    end

    resource "starlette" do
      url "https://files.pythonhosted.org/packages/88/2e/947cfe02def9371c07cd5bf5b6b61c829e9aecb9904db02a66cfafbc1eec/starlette-1.10.0-py3-none-any.whl"
      sha256 "478c0ab3b4ced6e82719849c118fa406f0278a3499c1a898cd15cd31bdc38ce4"
    end

    resource "typing_extensions" do
      url "https://files.pythonhosted.org/packages/49/d3/b8441a820a491ddfc024b0b0cf0393375b75ea13866d9c66727e54c2fc80/typing_extensions-4.16.0-py3-none-any.whl"
      sha256 "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8"
    end

    resource "typing_inspection" do
      url "https://files.pythonhosted.org/packages/de/0c/ea2544850a7c135e15033a5c7a8e7211136184b7ae63e2239d557c2b3019/typing_inspection-0.4.5-py3-none-any.whl"
      sha256 "bc210535442b39e1bf2805e0c7a17dfd6a4ace760c84c7f7d16245d23a6b1c39"
    end

  on_macos do
    on_arm do
    resource "cffi" do
      url "https://files.pythonhosted.org/packages/55/41/4c7042f317b9217502988f0873af87e16ad606dc20f84e546e3e6ce9764c/cffi-2.1.1-cp313-cp313-macosx_11_0_arm64.whl"
      sha256 "19ee6127ee34de7d83ce3d371ebc5ed91addbdcc39f9ab15ce4eb35a4e534971"
    end

    resource "cryptography" do
      url "https://files.pythonhosted.org/packages/e5/56/d194340cc4a57535e82e1bee9e89667ac4b7c13b5d3f59686deae3094dd5/cryptography-50.0.2-cp311-abi3-macosx_11_0_arm64.whl"
      sha256 "fa8f5efb344d6908a1ce62f4a24e2e5780f825d6f53f5f50ec5ffacac72936cb"
    end

    resource "greenlet" do
      url "https://files.pythonhosted.org/packages/f1/a1/e720a38852366c589e1a46cf570b886507ad2cf591050c203365638baab0/greenlet-3.5.6-cp313-cp313-macosx_11_0_universal2.whl"
      sha256 "f96f0e30b5a95c7631b12bfe214cbc90ec8fe8cfa36920596c10514a65743519"
    end

    resource "httptools" do
      url "https://files.pythonhosted.org/packages/9c/04/223994f8589750d2a36ceb43203e739cf75bd9e12c226680d73567766908/httptools-0.9.0-cp313-cp313-macosx_11_0_arm64.whl"
      sha256 "4fb995082fe41ec410b33c48b54fb1d44abb8a6ee762c31e8c42519e8c3a30a9"
    end

    resource "pydantic_core" do
      url "https://files.pythonhosted.org/packages/90/a9/fc89a632331882c4cb91b949003418e6f5085ddcf2c9b875d499682bca91/pydantic_core-2.50.4-cp313-cp313-macosx_11_0_arm64.whl"
      sha256 "1239daaf063e62213ca1f34d96663900bd7510c42a786e843fd328af70e46445"
    end

    resource "pyyaml" do
      url "https://files.pythonhosted.org/packages/b1/16/95309993f1d3748cd644e02e38b75d50cbc0d9561d21f390a76242ce073f/pyyaml-6.0.3-cp313-cp313-macosx_11_0_arm64.whl"
      sha256 "2283a07e2c21a2aa78d9c4442724ec1eb15f5e42a723b99cb3d822d48f5f7ad1"
    end

    resource "sqlalchemy" do
      url "https://files.pythonhosted.org/packages/f9/c0/8f160f3192899ec9e7fa6f6012975db03ebfd7940e759bf337940c6fa93a/sqlalchemy-2.1.9-cp313-cp313-macosx_11_0_arm64.whl"
      sha256 "21ac08d200391224caf30d7af1ab613ec9ad3a1e0a26c31a299c7698d6a10160"
    end

    resource "uvicorn" do
      url "https://files.pythonhosted.org/packages/38/0c/b54a4fdd7f90a3af8b02ebc9ce6712c2c208b7926a2f7bad95c33ebbe943/uvicorn-0.54.0-py3-none-any.whl"
      sha256 "505bdb0f318731d45f1f712071fc781a8981f6847a31c902c9f5e652d4f67faf"
    end

    resource "uvloop" do
      url "https://files.pythonhosted.org/packages/5f/83/eb980d64e6dd5da46d4dc35755fa6afd6b5b47141437cf89615f1117c5a6/uvloop-0.23.0-cp313-cp313-macosx_10_13_universal2.whl"
      sha256 "2dcff2d69be43e6559e5dad2c5a7a2dbfb60e05a77311b6c4b7a4a8123d86c65"
    end

    resource "watchfiles" do
      url "https://files.pythonhosted.org/packages/c7/8a/894799b485fe9473ad10422a0d9668e53fb78e3a2b5cc6061159572844ad/watchfiles-1.3.0-cp310-abi3-macosx_11_0_arm64.whl"
      sha256 "bbc1198edfdc90fda0600f825aa94150f428dfcbf8138746f55998e0e660d64c"
    end

    resource "websockets" do
      url "https://files.pythonhosted.org/packages/b3/65/098fd4d221d691395492fcba88c895dde19a51d371b06b8d0be71d3f781b/websockets-17.4-cp313-cp313-macosx_11_0_arm64.whl"
      sha256 "74e46409666c358b93fce0d8c6f4cb107d8dd7cba1302a38d49adf6fa8193c7e"
    end

    end
  end

  on_linux do
    resource "cffi" do
      url "https://files.pythonhosted.org/packages/95/95/86342356ff5953b3fb06f7ef7c5bee212d45e770abc7218d451b9148313c/cffi-2.1.1-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
      sha256 "a931079504ecc49efed7744c476a5c343a92fabf66dec2db95edb1b2fdc770e2"
    end

    resource "cryptography" do
      url "https://files.pythonhosted.org/packages/21/69/64cef1f702bf6657e0cc186ed1a2891d50d29fb41586b254e1c07adea261/cryptography-50.0.2-cp311-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
      sha256 "630ebfea3bf689d075f82316324ff7433dc447fe6bc1bfc76524b74b4a9567d2"
    end

    resource "greenlet" do
      url "https://files.pythonhosted.org/packages/f5/d7/826d0e080f0a7ad5ec47c8d143bbd3ca0887657bb806595fe2434d12938a/greenlet-3.2.5-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
      sha256 "752c896a8c976548faafe8a306d446c6a4c68d4fd24699b84d4393bd9ac69a8e"
    end

    resource "httptools" do
      url "https://files.pythonhosted.org/packages/af/71/ee32fd358f8a3bb199b03261f10921716990808a675d8160b5383487a317/httptools-0.6.4-cp313-cp313-manylinux_2_5_x86_64.manylinux1_x86_64.manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
      sha256 "4d87b29bd4486c0093fc64dea80231f7c7f7eb4dc70ae394d70a495ab8436071"
    end

    resource "pydantic_core" do
      url "https://files.pythonhosted.org/packages/2b/c0/1c8f2c8f1b03d3fe2fdd7962df8f5a744fe48c90b4c49615e4eb77d04141/pydantic_core-2.50.4-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.whl"
      sha256 "fb2bb5b557080da398b866408117d98fe9731a12334afd0cdff221b458cdc5dc"
    end

    resource "pyyaml" do
      url "https://files.pythonhosted.org/packages/74/27/e5b8f34d02d9995b80abcef563ea1f8b56d20134d8f4e5e81733b1feceb2/pyyaml-6.0.3-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl"
      sha256 "0f29edc409a6392443abf94b9cf89ce99889a1dd5376d94316ae5145dfedd5d6"
    end

    resource "sqlalchemy" do
      url "https://files.pythonhosted.org/packages/8a/cc/7fef310685d7d02637d838b410cb116d0748ad1b2ec545f8a6e94838cc9a/sqlalchemy-2.1.9-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl"
      sha256 "15fb00f016b72e4e89bff3cd3b71f95012882aa5493c6c8c92a46d40714fa0dc"
    end

    resource "uvicorn" do
      url "https://files.pythonhosted.org/packages/01/be/72532be3da7acc5fdfbccdb95215cd04f995a0886532a5b423f929cda4cc/uvicorn-0.48.0-py3-none-any.whl"
      sha256 "48097851328b87ec36117d3d575234519eb58c2b22d79666e9bbc6c49a761dad"
    end

    resource "uvloop" do
      url "https://files.pythonhosted.org/packages/98/54/b12915bebbf99d7ae0796211e7f5977b95f069830dca45dc1a346d84125d/uvloop-0.23.0-cp313-cp313-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl"
      sha256 "e2cba180d6451822763eda8364f342435a873bcfb3849cbd82fdeca248ca65eb"
    end

    resource "watchfiles" do
      url "https://files.pythonhosted.org/packages/8a/cf/e3ad894ed5909a7c44b0707e89bc25d19a3d78b3a7aec846119443b6ae56/watchfiles-1.3.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
      sha256 "b5768b49e426fd5b550b012c866db347cdf15c398ef98dc557b6e6b72fa74cd1"
    end

    resource "websockets" do
      url "https://files.pythonhosted.org/packages/eb/27/9db924cb0dbf22eade78d98fbae77790f9bf6bc729e6ab29aef9d68e4156/websockets-17.4-py3-none-any.whl"
      sha256 "c6bd2c9781915592b209160d0f017d4c7c82ad53075e6b0c24d2a89299e7f9e9"
    end

  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "overall_status", shell_output("#{bin}/keelway doctor --json")
  end
end
