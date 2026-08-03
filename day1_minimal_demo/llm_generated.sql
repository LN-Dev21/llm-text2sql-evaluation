SELECT
    s.student_name,
    ROUND(AVG(sc.score), 2) AS average_score
FROM students AS s
JOIN scores AS sc ON s.student_id = sc.student_id
GROUP BY s.student_id, s.student_name
HAVING AVG(sc.score) > 85
ORDER BY average_score DESC;

