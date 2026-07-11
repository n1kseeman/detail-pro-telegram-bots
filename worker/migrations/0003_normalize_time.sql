UPDATE appointments
SET time = time || ':00'
WHERE length(time) = 2 AND time GLOB '[0-2][0-9]';

UPDATE appointments
SET proposed_time = proposed_time || ':00'
WHERE proposed_time IS NOT NULL
  AND length(proposed_time) = 2
  AND proposed_time GLOB '[0-2][0-9]';
