-- Assume schema: bigquery-public-data.crypto_near_mainnet_us.receipt_actions (block_date DATE, action_kind STRING, receipt_receiver_account_id STRING)
-- Query: count distinct contract addresses (receipt_receiver_account_id) for FUNCTION_CALL actions per day
SELECT block_date, COUNT(DISTINCT receipt_receiver_account_id) AS value
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date BETWEEN @start_date AND @end_date
  AND action_kind = 'FUNCTION_CALL'
GROUP BY block_date
ORDER BY block_date
