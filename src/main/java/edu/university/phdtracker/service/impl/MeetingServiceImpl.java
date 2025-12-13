package edu.university.phdtracker.service.impl;

import edu.university.phdtracker.entity.Meeting;
import edu.university.phdtracker.repository.MeetingRepository;
import edu.university.phdtracker.service.MeetingService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
@Transactional
public class MeetingServiceImpl implements MeetingService {

    private final MeetingRepository meetingRepository;

    @Override
    public Meeting save(Meeting meeting) {
        return meetingRepository.save(meeting);
    }
}

