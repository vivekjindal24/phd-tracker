package edu.university.phdtracker.integration;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.time.Instant;

@Component
public class GoogleCalendarService {

    private static final Logger log = LoggerFactory.getLogger(GoogleCalendarService.class);

    public String createMeetingEvent(String supervisorEmail, String studentEmail, Instant meetingDate, String agenda) {
        // TODO Wire OAuth credentials and Google Calendar API client
        log.info("Creating Google Calendar event for supervisor {} and student {} on {}", supervisorEmail, studentEmail, meetingDate);
        return "mock-google-event-id";
    }
}

