CREATE OR REPLACE VIEW MODELING.DEMO_PERFORMANCE_BY_WEEKDAY AS
SELECT
    PUBLISHED_WEEKDAY,
    CASE CATEGORY_ID
        WHEN 1  THEN 'Film & Animation'
        WHEN 2  THEN 'Autos & Vehicles'
        WHEN 10 THEN 'Music'
        WHEN 15 THEN 'Pets & Animals'
        WHEN 17 THEN 'Sports'
        WHEN 19 THEN 'Travel & Events'
        WHEN 20 THEN 'Gaming'
        WHEN 22 THEN 'People & Blogs'
        WHEN 23 THEN 'Comedy'
        WHEN 24 THEN 'Entertainment'
        WHEN 25 THEN 'News & Politics'
        WHEN 26 THEN 'Howto & Style'
        WHEN 27 THEN 'Education'
        WHEN 28 THEN 'Science & Technology'
        WHEN 29 THEN 'Nonprofits & Activism'
        ELSE 'Other'
    END               AS CATEGORY_NAME,
    COUNT(*)          AS NUM_VIDEOS,
    AVG(VIEW_COUNT)   AS AVG_VIEWS,
    AVG(LIKE_COUNT)   AS AVG_LIKES
FROM MODELING.VIDEOS_TRAINING_DATA
GROUP BY PUBLISHED_WEEKDAY, CATEGORY_NAME;

CREATE OR REPLACE VIEW MODELING.DEMO_PERFORMANCE_BY_CATEGORY AS
SELECT
    CASE CATEGORY_ID
        WHEN 1  THEN 'Film & Animation'
        WHEN 2  THEN 'Autos & Vehicles'
        WHEN 10 THEN 'Music'
        WHEN 15 THEN 'Pets & Animals'
        WHEN 17 THEN 'Sports'
        WHEN 19 THEN 'Travel & Events'
        WHEN 20 THEN 'Gaming'
        WHEN 22 THEN 'People & Blogs'
        WHEN 23 THEN 'Comedy'
        WHEN 24 THEN 'Entertainment'
        WHEN 25 THEN 'News & Politics'
        WHEN 26 THEN 'Howto & Style'
        WHEN 27 THEN 'Education'
        WHEN 28 THEN 'Science & Technology'
        WHEN 29 THEN 'Nonprofits & Activism'
        ELSE 'Other'
    END             AS CATEGORY_NAME,
    COUNT(*)        AS NUM_VIDEOS,
    AVG(VIEW_COUNT) AS AVG_VIEWS
FROM MODELING.VIDEOS_TRAINING_DATA
GROUP BY CATEGORY_NAME
ORDER BY AVG_VIEWS DESC;

CREATE OR REPLACE VIEW MODELING.DEMO_TITLE_LENGTH_VS_VIEWS AS
SELECT
    LENGTH(TITLE) AS TITLE_LENGTH,
    VIEW_COUNT,
    CASE CATEGORY_ID
        WHEN 1  THEN 'Film & Animation'
        WHEN 2  THEN 'Autos & Vehicles'
        WHEN 10 THEN 'Music'
        WHEN 15 THEN 'Pets & Animals'
        WHEN 17 THEN 'Sports'
        WHEN 19 THEN 'Travel & Events'
        WHEN 20 THEN 'Gaming'
        WHEN 22 THEN 'People & Blogs'
        WHEN 23 THEN 'Comedy'
        WHEN 24 THEN 'Entertainment'
        WHEN 25 THEN 'News & Politics'
        WHEN 26 THEN 'Howto & Style'
        WHEN 27 THEN 'Education'
        WHEN 28 THEN 'Science & Technology'
        WHEN 29 THEN 'Nonprofits & Activism'
        ELSE 'Other'
    END           AS CATEGORY_NAME
FROM MODELING.VIDEOS_TRAINING_DATA;

CREATE OR REPLACE VIEW MODELING.DEMO_KPI_SUMMARY AS
SELECT
    CASE CATEGORY_ID
        WHEN 1  THEN 'Film & Animation'
        WHEN 2  THEN 'Autos & Vehicles'
        WHEN 10 THEN 'Music'
        WHEN 15 THEN 'Pets & Animals'
        WHEN 17 THEN 'Sports'
        WHEN 19 THEN 'Travel & Events'
        WHEN 20 THEN 'Gaming'
        WHEN 22 THEN 'People & Blogs'
        WHEN 23 THEN 'Comedy'
        WHEN 24 THEN 'Entertainment'
        WHEN 25 THEN 'News & Politics'
        WHEN 26 THEN 'Howto & Style'
        WHEN 27 THEN 'Education'
        WHEN 28 THEN 'Science & Technology'
        WHEN 29 THEN 'Nonprofits & Activism'
        ELSE 'Other'
    END                   AS CATEGORY_NAME,
    COUNT(*)              AS TOTAL_VIDEOS,
    AVG(VIEW_COUNT)       AS AVG_VIEWS,
    AVG(LIKE_COUNT)       AS AVG_LIKES,
    AVG(COMMENT_COUNT)    AS AVG_COMMENTS
FROM MODELING.VIDEOS_TRAINING_DATA
GROUP BY CATEGORY_NAME;
