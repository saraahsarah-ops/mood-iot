-- Seed daily_aggregates for Marie, Lea, Anna (14 days each)
-- Sophie already has data from tests

-- Marie
INSERT INTO daily_aggregates (id, patient_id, date, heart_rate_avg, heart_rate_variability, sleep_duration_min, sleep_quality_score, step_count, gps_radius_km, screen_time_min, call_count, call_duration_min, source_platform, synced_at) VALUES
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-19', 76, 38, 480, 6.5, 5200, 3.2, 280, 3, 12, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-20', 78, 36, 510, 6.8, 4800, 2.8, 300, 2, 8, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-21', 74, 40, 460, 6.2, 5500, 3.5, 260, 4, 15, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-22', 79, 35, 520, 7.0, 4500, 2.5, 310, 2, 7, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-23', 75, 39, 470, 6.3, 5100, 3.0, 275, 3, 10, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-24', 77, 37, 490, 6.6, 4900, 2.9, 290, 2, 9, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-25', 73, 41, 450, 6.0, 5800, 3.8, 250, 5, 18, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-26', 80, 34, 530, 7.2, 4200, 2.3, 320, 1, 5, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-27', 76, 38, 475, 6.4, 5300, 3.1, 285, 3, 11, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-28', 72, 42, 440, 5.8, 6000, 4.0, 240, 4, 16, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-29', 78, 36, 500, 6.7, 4700, 2.7, 295, 2, 8, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-30', 75, 39, 465, 6.1, 5400, 3.3, 270, 3, 13, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-03-31', 77, 37, 495, 6.5, 5000, 3.0, 288, 2, 9, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000002', '2026-04-01', 74, 40, 455, 6.0, 5600, 3.4, 265, 4, 14, 'android_health_connect', now());

-- Lea
INSERT INTO daily_aggregates (id, patient_id, date, heart_rate_avg, heart_rate_variability, sleep_duration_min, sleep_quality_score, step_count, gps_radius_km, screen_time_min, call_count, call_duration_min, source_platform, synced_at) VALUES
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-19', 65, 52, 450, 8.2, 8500, 5.2, 180, 5, 20, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-20', 67, 50, 440, 8.0, 8200, 4.8, 190, 4, 18, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-21', 64, 53, 460, 8.4, 8800, 5.5, 170, 6, 22, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-22', 66, 51, 445, 8.1, 8400, 5.0, 185, 5, 19, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-23', 63, 54, 455, 8.3, 8700, 5.3, 175, 6, 21, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-24', 68, 49, 435, 7.8, 7900, 4.5, 200, 4, 16, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-25', 64, 53, 465, 8.5, 9100, 5.7, 165, 7, 25, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-26', 66, 51, 448, 8.0, 8300, 5.1, 188, 5, 18, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-27', 65, 52, 452, 8.2, 8600, 5.4, 178, 5, 20, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-28', 63, 55, 470, 8.6, 9300, 5.8, 160, 7, 26, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-29', 67, 50, 442, 8.1, 8100, 4.9, 192, 4, 17, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-30', 65, 52, 455, 8.3, 8500, 5.2, 180, 5, 20, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-03-31', 66, 51, 447, 8.0, 8350, 5.0, 185, 5, 19, 'ios_healthkit', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000003', '2026-04-01', 64, 53, 458, 8.4, 8700, 5.4, 172, 6, 22, 'ios_healthkit', now());

-- Anna
INSERT INTO daily_aggregates (id, patient_id, date, heart_rate_avg, heart_rate_variability, sleep_duration_min, sleep_quality_score, step_count, gps_radius_km, screen_time_min, call_count, call_duration_min, source_platform, synced_at) VALUES
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-19', 82, 32, 340, 5.0, 3800, 2.0, 360, 2, 6, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-20', 85, 30, 320, 4.6, 3500, 1.8, 380, 1, 4, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-21', 80, 34, 360, 5.4, 4200, 2.3, 340, 3, 9, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-22', 84, 31, 325, 4.8, 3600, 1.9, 375, 1, 3, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-23', 81, 33, 350, 5.2, 4000, 2.1, 355, 2, 7, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-24', 86, 29, 310, 4.4, 3300, 1.7, 395, 1, 3, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-25', 79, 35, 370, 5.6, 4500, 2.5, 330, 3, 10, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-26', 87, 28, 300, 4.2, 3100, 1.5, 410, 0, 0, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-27', 83, 32, 345, 5.1, 3900, 2.0, 365, 2, 6, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-28', 78, 36, 380, 5.8, 4700, 2.6, 320, 4, 12, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-29', 85, 30, 315, 4.5, 3400, 1.8, 385, 1, 4, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-30', 82, 33, 355, 5.3, 4100, 2.2, 350, 2, 7, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-03-31', 84, 31, 330, 4.7, 3700, 1.9, 370, 1, 5, 'android_health_connect', now()),
(gen_random_uuid(), 'c0000000-0000-0000-0000-000000000004', '2026-04-01', 80, 34, 365, 5.5, 4300, 2.4, 335, 3, 9, 'android_health_connect', now());
