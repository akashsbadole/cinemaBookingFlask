"""
Integration Tests for Cinema Management System
Tests end-to-end workflows across all modules
"""

import unittest
import json
from datetime import datetime, date, timedelta
from app import create_app, db
from app.auth.models import User
from app.movies.models import Movie
from app.screens.models import Screen, Seat
from app.shows.models import Show
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment
from app.integration.service import IntegrationService
from app.integration.workflows import BookingWorkflow, ReportingWorkflow
from app.integration.search import GlobalSearchService
from app.integration.notifications import NotificationService, NotificationType


class IntegrationTestCase(unittest.TestCase):
    """Base class for integration tests"""
    
    def setUp(self):
        """Set up test environment"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create test user
        self.test_user = User(
            username='testuser',
            email='test@example.com',
            role='cashier'
        )
        self.test_user.set_password('testpass123')
        db.session.add(self.test_user)
        db.session.commit()
        
        # Create admin user
        self.admin_user = User(
            username='admin',
            email='admin@example.com',
            role='admin'
        )
        self.admin_user.set_password('adminpass123')
        db.session.add(self.admin_user)
        db.session.commit()
        
        # Create test movie
        self.test_movie = Movie(
            name='Test Movie',
            description='Test Description',
            duration=120,
            genre='Action',
            language='English',
            status='active'
        )
        db.session.add(self.test_movie)
        db.session.commit()
        
        # Create test screen
        self.test_screen = Screen(
            name='Test Screen',
            total_rows=5,
            total_columns=8
        )
        db.session.add(self.test_screen)
        db.session.commit()
        
        # Generate seats for screen
        self.test_screen.generate_seats('regular', 100.00, 150.00, 200.00)
        
        # Create test show
        self.test_show = Show(
            movie_id=self.test_movie.id,
            screen_id=self.test_screen.id,
            show_date=date.today() + timedelta(days=1),
            show_time=datetime.strptime('18:00', '%H:%M').time(),
            end_time=datetime.strptime('20:00', '%H:%M').time(),
            base_price=150.00,
            show_type='evening'
        )
        db.session.add(self.test_show)
        db.session.commit()
        
        self.client = self.app.test_client()
    
    def tearDown(self):
        """Clean up test environment"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()


class DashboardIntegrationTests(IntegrationTestCase):
    """Test dashboard integration"""
    
    def test_get_dashboard_statistics(self):
        """Test getting comprehensive dashboard statistics"""
        stats = IntegrationService.get_dashboard_statistics()
        
        self.assertIn('movies', stats)
        self.assertIn('screens', stats)
        self.assertIn('shows', stats)
        self.assertIn('bookings', stats)
        self.assertIn('payments', stats)
        self.assertIn('users', stats)
        self.assertIn('system_health', stats)
        
        # Check specific values
        self.assertEqual(stats['movies']['active'], 1)
        self.assertEqual(stats['screens']['total'], 1)
        self.assertEqual(stats['users']['active'], 2)


class BookingWorkflowTests(IntegrationTestCase):
    """Test complete booking workflow"""
    
    def test_get_available_movies(self):
        """Test getting available movies"""
        movies = BookingWorkflow.get_available_movies()
        
        self.assertEqual(len(movies), 1)
        self.assertEqual(movies[0]['id'], self.test_movie.id)
        self.assertEqual(movies[0]['title'], 'Test Movie')
    
    def test_get_movie_shows(self):
        """Test getting shows for a movie"""
        shows = BookingWorkflow.get_movie_shows(self.test_movie.id)
        
        self.assertEqual(len(shows), 1)
        self.assertEqual(shows[0]['id'], self.test_show.id)
        self.assertEqual(shows[0]['movie_title'], 'Test Movie')
        self.assertEqual(shows[0]['screen_name'], 'Test Screen')
    
    def test_get_show_seat_layout(self):
        """Test getting seat layout for a show"""
        seat_layout = BookingWorkflow.get_show_seat_layout(self.test_show.id)
        
        self.assertIn('seat_layout', seat_layout)
        self.assertIn('seat_types', seat_layout)
        self.assertEqual(seat_layout['total_seats'], 40)  # 5 rows x 8 columns
        self.assertEqual(seat_layout['available_seats'], 40)
        self.assertEqual(seat_layout['occupied_seats'], 0)
    
    def test_reserve_seats(self):
        """Test reserving seats"""
        # Get first seat
        seat = Seat.query.first()
        
        result = BookingWorkflow.reserve_seats(
            self.test_show.id, [seat.id], self.test_user.id
        )
        
        self.assertTrue(result['success'])
        self.assertIn('locked_seats', result)
        self.assertEqual(len(result['locked_seats']), 1)
    
    def test_create_booking(self):
        """Test creating a booking"""
        # Get first seat
        seat = Seat.query.first()
        
        # Reserve seat first
        BookingWorkflow.reserve_seats(
            self.test_show.id, [seat.id], self.test_user.id
        )
        
        # Create booking
        customer_info = {
            'customer_name': 'John Doe',
            'customer_phone': '1234567890',
            'customer_email': 'john@example.com',
            'payment_method': 'cash'
        }
        
        result = BookingWorkflow.create_booking(
            self.test_show.id, [seat.id], customer_info, self.test_user.id
        )
        
        self.assertTrue(result['success'])
        self.assertIn('booking_id', result)
        self.assertIn('reference_number', result)
        self.assertIn('total_amount', result)
    
    def test_process_payment(self):
        """Test processing payment"""
        # Create booking first
        seat = Seat.query.first()
        BookingWorkflow.reserve_seats(
            self.test_show.id, [seat.id], self.test_user.id
        )
        
        customer_info = {
            'customer_name': 'John Doe',
            'customer_phone': '1234567890',
            'customer_email': 'john@example.com',
            'payment_method': 'cash'
        }
        
        booking_result = BookingWorkflow.create_booking(
            self.test_show.id, [seat.id], customer_info, self.test_user.id
        )
        
        # Process payment
        payment_info = {
            'mode': 'cash',
            'reference_id': 'CASH001'
        }
        
        payment_result = BookingWorkflow.process_payment(
            booking_result['booking_id'], payment_info, self.test_user.id
        )
        
        self.assertTrue(payment_result['success'])
        self.assertIn('payment_id', payment_result)
        self.assertEqual(payment_result['status'], 'completed')
    
    def test_complete_booking_workflow(self):
        """Test complete booking workflow end-to-end"""
        seat = Seat.query.first()
        
        customer_info = {
            'customer_name': 'Jane Doe',
            'customer_phone': '9876543210',
            'customer_email': 'jane@example.com',
            'payment_method': 'card'
        }
        
        payment_info = {
            'mode': 'card',
            'card_type': 'visa',
            'card_last_4': '1234',
            'card_expiry_month': '12',
            'card_expiry_year': '2025'
        }
        
        result = BookingWorkflow.complete_booking_workflow(
            self.test_movie.id,
            self.test_show.id,
            [seat.id],
            customer_info,
            payment_info,
            self.test_user.id
        )
        
        self.assertTrue(result['success'])
        self.assertIn('booking_id', result)
        self.assertIn('payment_id', result)
        self.assertIn('reference_number', result)
    
    def test_cancel_booking(self):
        """Test cancelling a booking"""
        # Create booking first
        seat = Seat.query.first()
        BookingWorkflow.reserve_seats(
            self.test_show.id, [seat.id], self.test_user.id
        )
        
        customer_info = {
            'customer_name': 'Test User',
            'customer_phone': '5555555555',
            'customer_email': 'test@example.com',
            'payment_method': 'cash'
        }
        
        booking_result = BookingWorkflow.create_booking(
            self.test_show.id, [seat.id], customer_info, self.test_user.id
        )
        
        # Cancel booking
        result = BookingWorkflow.cancel_booking(
            booking_result['booking_id'], self.test_user.id, 'Customer request'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('reference_number', result)


class GlobalSearchTests(IntegrationTestCase):
    """Test global search functionality"""
    
    def test_global_search_movies(self):
        """Test searching movies"""
        results = GlobalSearchService.search('Test Movie', {'module_type': 'movies'})
        
        self.assertIn('modules', results)
        self.assertIn('movies', results['modules'])
        self.assertEqual(len(results['modules']['movies']), 1)
        self.assertEqual(results['modules']['movies'][0]['title'], 'Test Movie')
    
    def test_global_search_screens(self):
        """Test searching screens"""
        results = GlobalSearchService.search('Test Screen', {'module_type': 'screens'})
        
        self.assertIn('screens', results['modules'])
        self.assertEqual(len(results['modules']['screens']), 1)
        self.assertEqual(results['modules']['screens'][0]['name'], 'Test Screen')
    
    def test_advanced_search_bookings(self):
        """Test advanced search for bookings"""
        # Create a booking first
        seat = Seat.query.first()
        BookingWorkflow.reserve_seats(
            self.test_show.id, [seat.id], self.test_user.id
        )
        
        customer_info = {
            'customer_name': 'Search Test',
            'customer_phone': '1111111111',
            'customer_email': 'search@example.com',
            'payment_method': 'cash'
        }
        
        booking_result = BookingWorkflow.create_booking(
            self.test_show.id, [seat.id], customer_info, self.test_user.id
        )
        
        # Search for the booking
        search_params = {
            'module_type': 'bookings',
            'customer_name': 'Search Test',
            'reference_number': booking_result['reference_number']
        }
        
        results = GlobalSearchService.advanced_search(search_params)
        
        self.assertIn('bookings', results['modules'])
        self.assertEqual(len(results['modules']['bookings']), 1)
        self.assertEqual(
            results['modules']['bookings'][0]['reference_number'],
            booking_result['reference_number']
        )
    
    def test_search_suggestions(self):
        """Test search suggestions"""
        suggestions = GlobalSearchService.get_search_suggestions('Test', 'movies')
        
        self.assertIn('suggestions', suggestions)
        self.assertIn('movies', suggestions['suggestions'])
        self.assertIn('Test Movie', suggestions['suggestions']['movies'])


class NotificationTests(IntegrationTestCase):
    """Test notification system"""
    
    def test_create_notification(self):
        """Test creating a notification"""
        notification = NotificationService.create_notification(
            title='Test Notification',
            message='This is a test notification',
            notification_type=NotificationType.SYSTEM_ALERT,
            user_id=self.test_user.id
        )
        
        self.assertIsNotNone(notification)
        self.assertEqual(notification.title, 'Test Notification')
        self.assertEqual(notification.user_id, self.test_user.id)
    
    def test_get_user_notifications(self):
        """Test getting user notifications"""
        # Create a notification
        NotificationService.create_notification(
            title='Test Notification',
            message='This is a test notification',
            notification_type=NotificationType.SYSTEM_ALERT,
            user_id=self.test_user.id
        )
        
        notifications = NotificationService.get_user_notifications(self.test_user.id)
        
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, 'Test Notification')
    
    def test_booking_notification(self):
        """Test booking confirmation notification"""
        # Create a booking
        seat = Seat.query.first()
        BookingWorkflow.reserve_seats(
            self.test_show.id, [seat.id], self.test_user.id
        )
        
        customer_info = {
            'customer_name': 'Notification Test',
            'customer_phone': '2222222222',
            'customer_email': 'notify@example.com',
            'payment_method': 'cash'
        }
        
        booking_result = BookingWorkflow.create_booking(
            self.test_show.id, [seat.id], customer_info, self.test_user.id
        )
        
        # Trigger notification
        NotificationService.notify_booking_confirmed(booking_result['booking_id'])
        
        # Check notification was created
        notifications = NotificationService.get_user_notifications(self.test_user.id)
        booking_notifications = [
            n for n in notifications 
            if n.notification_type == NotificationType.BOOKING_CONFIRMED
        ]
        
        self.assertEqual(len(booking_notifications), 1)
    
    def test_payment_notification(self):
        """Test payment completion notification"""
        # Create booking and payment
        seat = Seat.query.first()
        BookingWorkflow.reserve_seats(
            self.test_show.id, [seat.id], self.test_user.id
        )
        
        customer_info = {
            'customer_name': 'Payment Test',
            'customer_phone': '3333333333',
            'customer_email': 'payment@example.com',
            'payment_method': 'card'
        }
        
        booking_result = BookingWorkflow.create_booking(
            self.test_show.id, [seat.id], customer_info, self.test_user.id
        )
        
        payment_info = {'mode': 'card', 'card_type': 'visa'}
        payment_result = BookingWorkflow.process_payment(
            booking_result['booking_id'], payment_info, self.test_user.id
        )
        
        # Trigger notification
        NotificationService.notify_payment_completed(payment_result['payment_id'])
        
        # Check notification was created
        notifications = NotificationService.get_user_notifications(self.test_user.id)
        payment_notifications = [
            n for n in notifications 
            if n.notification_type == NotificationType.PAYMENT_COMPLETED
        ]
        
        self.assertEqual(len(payment_notifications), 1)


class DataIntegrityTests(IntegrationTestCase):
    """Test data integrity checks"""
    
    def test_validate_data_integrity(self):
        """Test comprehensive data integrity validation"""
        results = IntegrationService.validate_data_integrity()
        
        self.assertIn('checks', results)
        self.assertIn('module_checks', results)
        self.assertIn('summary', results)
        
        # Check module-specific checks
        self.assertIn('movie_show_integrity', results['module_checks'])
        self.assertIn('screen_seat_integrity', results['module_checks'])
        self.assertIn('booking_payment_integrity', results['module_checks'])
        self.assertIn('show_schedule_integrity', results['module_checks'])
    
    def test_cascade_delete_movie(self):
        """Test cascade delete movie"""
        # Create another show for the movie
        future_show = Show(
            movie_id=self.test_movie.id,
            screen_id=self.test_screen.id,
            show_date=date.today() + timedelta(days=2),
            show_time=datetime.strptime('20:00', '%H:%M').time(),
            end_time=datetime.strptime('22:00', '%H:%M').time(),
            base_price=150.00,
            show_type='night'
        )
        db.session.add(future_show)
        db.session.commit()
        
        # Delete movie
        result = IntegrationService.cascade_delete_movie(self.test_movie.id)
        
        self.assertTrue(result['success'])
        self.assertIn('deleted_shows', result)
        self.assertEqual(result['deleted_shows'], 2)
    
    def test_cascade_delete_screen(self):
        """Test cascade delete screen"""
        # Delete screen
        result = IntegrationService.cascade_delete_screen(self.test_screen.id)
        
        self.assertTrue(result['success'])
        self.assertIn('deleted_seats', result)
        self.assertEqual(result['deleted_seats'], 40)  # 5 rows x 8 columns


class ReportingTests(IntegrationTestCase):
    """Test reporting functionality"""
    
    def test_generate_daily_report(self):
        """Test generating daily report"""
        # Create some test data
        seat = Seat.query.first()
        BookingWorkflow.reserve_seats(
            self.test_show.id, [seat.id], self.test_user.id
        )
        
        customer_info = {
            'customer_name': 'Report Test',
            'customer_phone': '4444444444',
            'customer_email': 'report@example.com',
            'payment_method': 'cash'
        }
        
        booking_result = BookingWorkflow.create_booking(
            self.test_show.id, [seat.id], customer_info, self.test_user.id
        )
        
        payment_info = {'mode': 'cash'}
        BookingWorkflow.process_payment(
            booking_result['booking_id'], payment_info, self.test_user.id
        )
        
        # Generate report
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        report = ReportingWorkflow.generate_comprehensive_report(
            today, tomorrow, 'daily'
        )
        
        self.assertIn('report_type', report)
        self.assertEqual(report['report_type'], 'daily')
        self.assertIn('period', report)
        self.assertIn('daily_sales', report)
        self.assertIn('payment_methods', report)
    
    def test_export_report_to_csv(self):
        """Test exporting report to CSV"""
        # Create test report data
        report_data = {
            'report_type': 'test',
            'period': {
                'start_date': '2023-01-01',
                'end_date': '2023-01-02'
            },
            'daily_sales': [
                {
                    'date': '2023-01-01',
                    'sales': [
                        {
                            'movie_title': 'Test Movie',
                            'screen_name': 'Test Screen',
                            'bookings_count': 1,
                            'revenue': 150.0,
                            'tickets_sold': 1
                        }
                    ]
                }
            ]
        }
        
        result = ReportingWorkflow.export_report_to_csv(report_data, 'test_report.csv')
        
        self.assertTrue(result['success'])
        self.assertIn('filename', result)


if __name__ == '__main__':
    unittest.main()