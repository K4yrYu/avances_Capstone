-- Elimina exclusivamente los 24 productos de quincallería agregados por SFI.
-- No afecta pinturas ni otros productos. Revisa primero el SELECT.
START TRANSACTION;

SELECT id, sku, nombre
FROM productos_producto
WHERE sku IN (
  'SFI-QUI-TOR-001', 'SFI-QUI-TOR-002', 'SFI-QUI-TOR-003',
  'SFI-QUI-TOR-004', 'SFI-QUI-TOR-005', 'SFI-QUI-TOR-006',
  'SFI-QUI-ANC-001', 'SFI-QUI-ANC-002', 'SFI-QUI-ANC-003',
  'SFI-QUI-ANC-004', 'SFI-QUI-ANC-005', 'SFI-QUI-ANC-006',
  'SFI-QUI-SEG-001', 'SFI-QUI-SEG-002', 'SFI-QUI-SEG-003',
  'SFI-QUI-SEG-004', 'SFI-QUI-SEG-005', 'SFI-QUI-SEG-006',
  'SFI-QUI-HER-001', 'SFI-QUI-HER-002', 'SFI-QUI-HER-003',
  'SFI-QUI-HER-004', 'SFI-QUI-HER-005', 'SFI-QUI-HER-006'
);

DELETE FROM productos_producto
WHERE sku IN (
  'SFI-QUI-TOR-001', 'SFI-QUI-TOR-002', 'SFI-QUI-TOR-003',
  'SFI-QUI-TOR-004', 'SFI-QUI-TOR-005', 'SFI-QUI-TOR-006',
  'SFI-QUI-ANC-001', 'SFI-QUI-ANC-002', 'SFI-QUI-ANC-003',
  'SFI-QUI-ANC-004', 'SFI-QUI-ANC-005', 'SFI-QUI-ANC-006',
  'SFI-QUI-SEG-001', 'SFI-QUI-SEG-002', 'SFI-QUI-SEG-003',
  'SFI-QUI-SEG-004', 'SFI-QUI-SEG-005', 'SFI-QUI-SEG-006',
  'SFI-QUI-HER-001', 'SFI-QUI-HER-002', 'SFI-QUI-HER-003',
  'SFI-QUI-HER-004', 'SFI-QUI-HER-005', 'SFI-QUI-HER-006'
);

SELECT ROW_COUNT() AS registros_eliminados;

-- Usa COMMIT para confirmar o ROLLBACK para cancelar después de revisar el resultado.
-- COMMIT;
-- ROLLBACK;
