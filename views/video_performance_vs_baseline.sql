CREATE OR REPLACE VIEW VIDEO_PERFORMANCE_VS_BASELINE AS
WITH windowed AS (
    SELECT
        VIDEO_ID,
        CHANNEL_ID,
        TITLE,
        VIEW_COUNT,
        SUM(VIEW_COUNT) OVER (PARTITION BY CHANNEL_ID) AS channel_total_views,
        COUNT(*)        OVER (PARTITION BY CHANNEL_ID) AS channel_video_count
    FROM VIDEOS
)
SELECT
    VIDEO_ID,
    CHANNEL_ID,
    TITLE,
    VIEW_COUNT,
    channel_video_count - 1                                                  AS num_comparison_videos,
    (channel_total_views - VIEW_COUNT)
        / NULLIF(channel_video_count - 1, 0)                                 AS channel_avg_excl_self,
    VIEW_COUNT
        / NULLIF(
            (channel_total_views - VIEW_COUNT)
                / NULLIF(channel_video_count - 1, 0),
            0
          )                                                                   AS performance_ratio
FROM windowed;
