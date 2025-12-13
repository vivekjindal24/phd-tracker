package edu.university.phdtracker.service;

import edu.university.phdtracker.dto.MeetingRequest;
import edu.university.phdtracker.dto.MeetingResponse;
import edu.university.phdtracker.dto.SupervisorReportResponse;
import edu.university.phdtracker.dto.SupervisorStudentRequest;
import edu.university.phdtracker.dto.SupervisorStudentResponse;

import java.util.List;

public interface SupervisorService {

    SupervisorStudentResponse addStudent(Long supervisorId, SupervisorStudentRequest request);

    List<SupervisorStudentResponse> getStudents(Long supervisorId);

    MeetingResponse scheduleMeeting(MeetingRequest request);

    SupervisorReportResponse generateReport(Long supervisorId, Long studentId);
}

