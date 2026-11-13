-- sql/active_accounts_daily.sql
-- Assumed schema for NEAR BigQuery public dataset
-- Dataset: bigquery-public-data.crypto_near_mainnet_us
-- Table: transactions
-- Columns: block_date (DATE, partition), signer_account_id, transaction_hash
-- Filters on block_date using query parameters @start_date and @end_date (DATE)
-- Output: row per day with distinct signer account count

SELECT
    block_date,
    COUNT(DISTINCT signer_account_id) AS value
FROM
    `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE
    block_date BETWEEN @start_date AND @end_date
GROUP BY
    block_date
ORDER BY
    block_date
