-- PhD Tracker Sample Data
-- Passwords are BCrypt-encoded (default: "password123")

-- Clear existing data (optional, for testing)
-- DELETE FROM notifications;
-- DELETE FROM meetings;
-- DELETE FROM documents;
-- DELETE FROM milestones;
-- DELETE FROM students;
-- DELETE FROM supervisors;
-- DELETE FROM users;

-- Insert Users
-- Admin: admin@phd.edu / password123
INSERT INTO users (id, name, email, password, role, whatsapp_number, created_at) VALUES
(1, 'Admin User', 'admin@phd.edu', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'ADMIN', '+1234567890', NOW());

-- Supervisors: prof1@phd.edu / password123, prof2@phd.edu / password123
INSERT INTO users (id, name, email, password, role, whatsapp_number, created_at) VALUES
(2, 'Prof. John Smith', 'prof1@phd.edu', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'SUPERVISOR', '+1234567891', NOW()),
(3, 'Prof. Emily Davis', 'prof2@phd.edu', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'SUPERVISOR', '+1234567892', NOW());

-- Students: student1@phd.edu / password123, student2@phd.edu / password123, student3@phd.edu / password123
INSERT INTO users (id, name, email, password, role, whatsapp_number, created_at) VALUES
(4, 'Alice Johnson', 'student1@phd.edu', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'STUDENT', '+1234567893', NOW()),
(5, 'Bob Williams', 'student2@phd.edu', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'STUDENT', '+1234567894', NOW()),
(6, 'Carol Brown', 'student3@phd.edu', '$2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy', 'STUDENT', '+1234567895', NOW());

-- Insert Supervisors
INSERT INTO supervisors (user_id, department) VALUES
(2, 'Computer Science'),
(3, 'Electrical Engineering');

-- Insert Students
INSERT INTO students (user_id, supervisor_id, enrollment_date, research_title, status) VALUES
(4, 2, '2023-09-01', 'Machine Learning Applications in Healthcare', 'ACTIVE'),
(5, 2, '2024-01-15', 'Blockchain for Supply Chain Management', 'ACTIVE'),
(6, 3, '2023-08-20', 'Energy-Efficient IoT Systems', 'ACTIVE');

-- Insert Milestones
INSERT INTO milestones (student_id, title, description, deadline, status, created_at) VALUES
(4, 'Literature Review', 'Complete comprehensive literature survey on ML in healthcare', '2024-03-15', 'COMPLETED', NOW()),
(4, 'Research Proposal Defense', 'Present and defend research proposal to committee', '2024-06-20', 'PENDING', NOW()),
(4, 'Prototype Development', 'Develop initial ML model prototype', '2024-09-30', 'PENDING', NOW()),
(5, 'Literature Review', 'Survey blockchain technologies in supply chain', '2024-04-10', 'COMPLETED', NOW()),
(5, 'System Design', 'Design blockchain-based supply chain architecture', '2024-07-15', 'PENDING', NOW()),
(6, 'Hardware Setup', 'Set up IoT testbed environment', '2024-02-28', 'COMPLETED', NOW()),
(6, 'Energy Analysis', 'Conduct energy consumption analysis', '2024-05-30', 'PENDING', NOW());

-- Insert Documents
INSERT INTO documents (student_id, file_name, version, uploaded_at) VALUES
(4, 'literature_review_draft.pdf', 'v1.0', NOW()),
(4, 'research_proposal.pdf', 'v2.1', NOW()),
(5, 'blockchain_survey.pdf', 'v1.0', NOW()),
(5, 'system_architecture.pdf', 'v1.5', NOW()),
(6, 'iot_testbed_setup.pdf', 'v1.0', NOW());

-- Insert Meetings
INSERT INTO meetings (supervisor_id, student_id, meeting_date, agenda, google_event_id) VALUES
(2, 4, '2024-12-20 10:00:00', 'Discuss literature review findings and next steps', 'mock-google-event-001'),
(2, 5, '2024-12-22 14:00:00', 'Review blockchain architecture design', 'mock-google-event-002'),
(3, 6, '2024-12-18 15:30:00', 'Review energy consumption analysis methodology', 'mock-google-event-003');

-- Insert Notifications
INSERT INTO notifications (user_id, message, channel, sent_at) VALUES
(4, 'Your milestone "Literature Review" has been approved by your supervisor', 'EMAIL', NOW()),
(4, 'Upcoming meeting scheduled for 2024-12-20 at 10:00 AM', 'WHATSAPP', NOW()),
(5, 'Your document "system_architecture.pdf" has been uploaded successfully', 'EMAIL', NOW()),
(6, 'Reminder: Energy Analysis milestone deadline is approaching (2024-05-30)', 'WHATSAPP', NOW());

