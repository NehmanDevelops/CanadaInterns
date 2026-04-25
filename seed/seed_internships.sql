-- Seed data: 10 fake Canadian internship listings for UI testing
INSERT INTO internships (title, company, location, description, posted_at) VALUES
('Software Developer Intern', 'MapleTech', 'Toronto, ON', 'Work on real-world web apps with a Canadian tech leader.', NOW() - INTERVAL '2 days'),
('Marketing Intern', 'True North Media', 'Vancouver, BC', 'Assist in digital campaigns for Canadian brands.', NOW() - INTERVAL '1 day'),
('Data Analyst Intern', 'Prairie Analytics', 'Calgary, AB', 'Analyze data trends for Canadian agriculture.', NOW() - INTERVAL '3 days'),
('Finance Intern', 'Bank of Canada', 'Ottawa, ON', 'Support financial modeling and reporting.', NOW() - INTERVAL '5 hours'),
('UX/UI Design Intern', 'RedLeaf Studios', 'Montreal, QC', 'Design user interfaces for Canadian startups.', NOW() - INTERVAL '6 hours'),
('Engineering Intern', 'Northern Rail', 'Winnipeg, MB', 'Work on infrastructure projects across Canada.', NOW() - INTERVAL '4 days'),
('Policy Research Intern', 'Gov of Canada', 'Ottawa, ON', 'Research and draft policy briefs.', NOW() - INTERVAL '1 day'),
('Environmental Science Intern', 'EcoCan', 'Victoria, BC', 'Assist with field research and reporting.', NOW() - INTERVAL '2 days'),
('Product Management Intern', 'StartupHub', 'Toronto, ON', 'Coordinate product launches and feedback.', NOW() - INTERVAL '3 hours'),
('Journalism Intern', 'The Canadian Press', 'Toronto, ON', 'Write and edit news stories for national syndication.', NOW() - INTERVAL '7 hours');