SELECT
    COUNT(*) AS total_results,
    COUNT(DISTINCT input_id) AS unique_processed_inputs
FROM result;

SELECT
    input_id,
    COUNT(*) AS appearances
FROM result
GROUP BY input_id
HAVING COUNT(*) > 1;

SELECT
    worker_identifier,
    COUNT(*) AS processed_records
FROM result
GROUP BY worker_identifier
ORDER BY worker_identifier;

SELECT
    i.id AS input_id,
    i.description,
    i.status,
    r.worker_identifier AS result_worker,
    r.date AS result_date,
    r.result
FROM input i
LEFT JOIN result r ON r.input_id = i.id
ORDER BY i.id;
