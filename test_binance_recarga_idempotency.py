#!/usr/bin/env python3
"""Prueba que una recarga Binance no acredite saldo dos veces."""

import os
import sqlite3
import threading


TEST_DB = 'test_binance_recarga_idempotency.db'


def setup_test_database():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row

    conn.execute('''
        CREATE TABLE usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            saldo REAL DEFAULT 0.0,
            bono_activo BOOLEAN DEFAULT FALSE
        )
    ''')
    conn.execute('''
        CREATE TABLE recargas_binance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            codigo_referencia TEXT NOT NULL UNIQUE,
            monto_solicitado REAL NOT NULL,
            monto_unico REAL NOT NULL,
            estado TEXT DEFAULT 'pendiente',
            binance_transaction_id TEXT,
            fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
            fecha_expiracion DATETIME NOT NULL,
            fecha_completada DATETIME,
            bonus REAL DEFAULT 0.0
        )
    ''')
    conn.execute('''
        CREATE TABLE creditos_billetera (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            monto REAL DEFAULT 0.0,
            saldo_anterior REAL DEFAULT 0.0,
            fecha DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute("CREATE UNIQUE INDEX idx_recargas_binance_txid_unique ON recargas_binance(binance_transaction_id) WHERE binance_transaction_id IS NOT NULL")

    conn.execute('INSERT INTO usuarios (saldo, bono_activo) VALUES (?, ?)', (100.0, False))
    conn.execute('''
        INSERT INTO recargas_binance (usuario_id, codigo_referencia, monto_solicitado, monto_unico, fecha_expiracion)
        VALUES (?, ?, ?, ?, datetime('now', '+10 minutes'))
    ''', (1, 'REC-TEST-001', 50.0, 50.0))
    conn.commit()
    conn.close()


def claim_and_credit(result_list, index, barrier):
    conn = sqlite3.connect(TEST_DB, timeout=5)
    conn.row_factory = sqlite3.Row

    try:
        barrier.wait()
        claim_result = conn.execute('''
            UPDATE recargas_binance
            SET estado = 'completada', binance_transaction_id = ?, fecha_completada = CURRENT_TIMESTAMP, bonus = ?
            WHERE id = ?
              AND estado = 'pendiente'
              AND (binance_transaction_id IS NULL OR binance_transaction_id = '')
        ''', ('BNX-123456', 0.0, 1))

        if claim_result.rowcount != 1:
            conn.rollback()
            result_list[index] = False
            return

        saldo_row = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (1,)).fetchone()
        saldo_anterior = saldo_row['saldo']
        conn.execute('UPDATE usuarios SET saldo = saldo + ? WHERE id = ?', (50.0, 1))
        conn.execute('''
            INSERT INTO creditos_billetera (usuario_id, monto, saldo_anterior)
            VALUES (?, ?, ?)
        ''', (1, 50.0, saldo_anterior))
        conn.commit()
        result_list[index] = True
    finally:
        conn.close()


def test_concurrent_claim_only_credits_once():
    setup_test_database()

    results = [None, None]
    barrier = threading.Barrier(2)
    threads = [
        threading.Thread(target=claim_and_credit, args=(results, 0, barrier)),
        threading.Thread(target=claim_and_credit, args=(results, 1, barrier)),
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    conn = sqlite3.connect(TEST_DB)
    conn.row_factory = sqlite3.Row
    saldo = conn.execute('SELECT saldo FROM usuarios WHERE id = ?', (1,)).fetchone()['saldo']
    creditos = conn.execute('SELECT COUNT(*) AS total FROM creditos_billetera').fetchone()['total']
    recarga = conn.execute('SELECT estado, binance_transaction_id FROM recargas_binance WHERE id = ?', (1,)).fetchone()
    conn.close()

    assert results.count(True) == 1, f'Se esperaba un solo ganador y se obtuvo: {results}'
    assert results.count(False) == 1, f'Se esperaba un solo rechazo y se obtuvo: {results}'
    assert saldo == 150.0, f'El saldo final debería ser 150.0 y fue {saldo}'
    assert creditos == 1, f'Solo debe existir un crédito registrado y hay {creditos}'
    assert recarga['estado'] == 'completada'
    assert recarga['binance_transaction_id'] == 'BNX-123456'


if __name__ == '__main__':
    test_concurrent_claim_only_credits_once()
    print('OK: la recarga Binance solo se acredita una vez incluso con dos verificadores simultáneos.')