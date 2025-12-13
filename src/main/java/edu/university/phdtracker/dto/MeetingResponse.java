package edu.university.phdtracker.dto;

import java.time.Instant;

public record MeetingResponse(
        Long id,
        Long supervisorId,
        Long studentId,
        Instant meetingDate,
        String agenda,
        String googleEventId
) {
}

