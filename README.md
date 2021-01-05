# submarine-destroyer

## 実行方法
```console
$ cd src/
$ python3 main.py
```


# コマンドラインオプション

- `-q`
このオプションが付与されたときに限り、自軍の配置の表示を抑制します。
このプログラムと対戦するためのオプションです。
(けど他の `[info]` ログメッセージで自軍の位置情報が表示されるのであまり意味ないかも...)

使用例:
```
$ python3 main.py -q
```

- `-n <integer>`
敵軍の潜水艦の初期個数を指定します。デバッグ用です。
このオプションが指定されない場合は、敵軍の潜水艦の初期個数はデフォルト値である 4 に設定します。
使用例:
```
$ python3 main.py -n 1
# 敵軍の潜水艦の初期個数を 1 に設定します。
```

## ファイル構成
```
/
├── README.md
│
└── src/
    │
    ├── bluedragon/
    │   │
    │   ├── __init__.py  ... 空ファイル。python モジュールのために必要。
    │   │
    │   ├── io.py        ... 対戦データの出力や、敵軍からの情報の入力など。
    │   │
    │   ├── logic.py     ... 対戦データの処理・自軍の操作の決定。
    │   │
    │   ├── rule.py      ... 対戦における不変の情報・ルール
    │   │
    │   └── model.py     ... 対戦データの構造や攻撃・移動情報の定義。
    │
    └── main.py  ... プログラムのエントリポイント。ゲームループ。
```

## ｷｮｴｴｴｴｴ

ｷｮｴｴｴｴｴｴｴｴ
