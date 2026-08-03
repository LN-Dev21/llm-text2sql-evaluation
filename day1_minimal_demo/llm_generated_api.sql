SELECT s.student_name, AVG(sc.score) AS average_score
FROM students s
JOIN scores sc ON s.student_id = sc.student_id
GROUP BY s.student_id, s.student_name
HAVING AVG(sc.score) > 85
ORDER BY average_score DESC;
