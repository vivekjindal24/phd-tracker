package edu.university.phdtracker.dto;

import java.util.List;

public record SupervisorReportResponse(
        Long studentId,
        String studentName,
        String researchTitle,
        String status,
        List<MilestoneResponse> milestones,
        List<DocumentResponse> documents,
        List<MeetingResponse> meetings
) {
}

