CREATE OR REPLACE VIEW BEST_DAY_TO_POST AS
WITH filtered AS (
    -- only weekdays with enough videos to be a pattern
    SELECT
        CHANNEL_ID,
        PUBLISHED_WEEKDAY,
        avg_lifetime_views,
        num_videos,
        ROW_NUMBER() OVER (
            PARTITION BY CHANNEL_ID
            ORDER BY avg_lifetime_views DESC, PUBLISHED_WEEKDAY
        )                                    AS rnk,
        COUNT(*) OVER (PARTITION BY CHANNEL_ID) AS qualifying_weekday_count
    FROM PERFORMANCE_BY_WEEKDAY
    WHERE num_videos >= 2
),
all_channels AS (
    SELECT DISTINCT CHANNEL_ID FROM PERFORMANCE_BY_WEEKDAY
)
SELECT
    ac.CHANNEL_ID,
    CASE
        WHEN f.qualifying_weekday_count >= 2 THEN f.PUBLISHED_WEEKDAY
    END                                          AS best_weekday,
    CASE
        WHEN f.qualifying_weekday_count >= 2 THEN f.avg_lifetime_views
    END                                          AS best_weekday_avg_views,
    COALESCE(f.qualifying_weekday_count >= 2, FALSE) AS has_sufficient_data
FROM all_channels ac
LEFT JOIN filtered f
    ON ac.CHANNEL_ID = f.CHANNEL_ID
   AND f.rnk = 1;
