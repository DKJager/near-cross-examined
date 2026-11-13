-- sql/transactions_daily.sql: NEAR BigQuery public dataset query for daily unique transactions
-- Assumed schema: bigquery-public-data.crypto_near_mainnet_us.transactions
--   block_date (DATE, partition column), signer_account_id, transaction_hash
--   receipt_actions: block_date, action_kind, receipt_receiver_account_id
SELECT block_date, COUNT(DISTINCT transaction_hash) AS value
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date BETWEEN @start_date AND @end_date
GROUP BY block_date
ORDER BY block_date
