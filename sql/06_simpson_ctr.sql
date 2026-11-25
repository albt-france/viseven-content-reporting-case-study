-- 06_simpson_ctr.sql: email click-through rate, DE vs PL, overall and by HCP segment (SIMULATED).
-- CTR = email_click / email_sent (approved content at event time), whole period.
CREATE OR REPLACE TABLE out_simpson AS
WITH b AS (SELECT * FROM fact_activity WHERE status_at_event = 'approved' AND channel = 'approved-email' AND market IN ('DE', 'PL')),
seg AS (SELECT market, segment, count(*) FILTER (WHERE kind = 'sent') AS sent, count(*) FILTER (WHERE kind = 'click') AS clicks,
               count(DISTINCT hcp_id) FILTER (WHERE kind = 'sent') AS hcps
        FROM b GROUP BY ALL),
tot AS (SELECT market, 'All' AS segment, sum(sent) AS sent, sum(clicks) AS clicks, sum(hcps) AS hcps FROM seg GROUP BY 1)
SELECT x.market, x.segment, x.sent, x.clicks, x.hcps, round(x.clicks / x.sent, 4) AS ctr,
       round(x.sent / sum(x.sent) FILTER (WHERE x.segment <> 'All') OVER (PARTITION BY x.market), 4) AS share_of_sends
FROM (SELECT * FROM seg UNION ALL SELECT * FROM tot) x ORDER BY x.segment, x.market;

-- Mix-standardised CTR: each market's segment CTRs weighted with the SAME segment mix (all 8 markets' sends)
CREATE OR REPLACE TABLE out_simpson_standardised AS
WITH mix AS (SELECT segment, count(*) FILTER (WHERE kind = 'sent') / sum(count(*) FILTER (WHERE kind = 'sent')) OVER () AS w
             FROM fact_activity WHERE status_at_event = 'approved' AND channel = 'approved-email' GROUP BY 1)
SELECT s.market, round(sum(s.ctr * m.w), 4) AS ctr_standardised,
       any_value((SELECT t.ctr FROM out_simpson t WHERE t.market = s.market AND t.segment = 'All')) AS ctr_raw
FROM out_simpson s JOIN mix m USING (segment)
WHERE s.segment <> 'All' GROUP BY 1 ORDER BY 1;
