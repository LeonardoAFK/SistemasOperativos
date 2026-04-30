DROP TABLE IF EXISTS result;
DROP TABLE IF EXISTS input;

CREATE TABLE input (
    id SERIAL PRIMARY KEY,
    description TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    worker_identifier VARCHAR(80),
    in_process_at TIMESTAMP,
    processed_at TIMESTAMP,
    CONSTRAINT input_status_check
        CHECK (status IN ('pending', 'in_process', 'processed'))
);

CREATE TABLE result (
    id SERIAL PRIMARY KEY,
    input_id INT NOT NULL REFERENCES input(id),
    worker_identifier VARCHAR(80) NOT NULL,
    result TEXT NOT NULL,
    date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT result_input_unique UNIQUE (input_id)
);

INSERT INTO input (description)
SELECT 'Dato de prueba #' || number
FROM generate_series(1, 200) AS number;

SELECT 'Database initialized successfully' AS message;
