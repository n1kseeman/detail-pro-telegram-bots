UPDATE sqlite_sequence
SET seq = (SELECT COALESCE(MAX(id), 0) FROM services)
WHERE name = 'services';
