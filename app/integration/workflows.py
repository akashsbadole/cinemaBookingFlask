"""
Workflow handlers for cinema management system
Implements complete end-to-end workflows across modules
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy import and_, or_, func
from flask import current_app

from app.database import db
from app.movies.models import Movie
from app.screens.models import Screen, Seat, SeatLock
from app.shows.models import Show
from app.bookings.models import Booking, BookingSeat
from app.payments.models import Payment, PaymentStatusHistory
from app.auth.models import User


class BookingWorkflow:
    """Complete booking workflow from movie selection to payment"""
    
    @staticmethod
    def get_available_movies(date: datetime.date = None) -> List[Dict[str, Any]]:
        """Get movies with available shows for the given date"""
        try:
            if date is None:
                date = datetime.now().date()
            
            # Get movies with shows on the given date
            movies = db.session.query(
                Movie.id,
                Movie.title,
                Movie.genre,
                Movie.language,
                Movie.duration,
                Movie.rating,
                func.count(Show.id).label('show_count')
            ).join(
                Show, Movie.id == Show.movie_id
            ).filter(
                Movie.status == 'active',
                Show.show_date == date,
                Show.status == 'scheduled'
            ).group_by(
                Movie.id, Movie.title, Movie.genre, Movie.language, Movie.duration, Movie.rating
            ).all()
            
            return [
                {
                    'id': movie.id,
                    'title': movie.title,
                    'genre': movie.genre,
                    'language': movie.language,
                    'duration': movie.duration,
                    'rating': movie.rating,
                    'show_count': movie.show_count
                }
                for movie in movies
            ]
            
        except Exception as e:
            current_app.logger.error(f"Error getting available movies: {str(e)}")
            return []
    
    @staticmethod
    def get_movie_shows(movie_id: int, date: datetime.date = None) -> List[Dict[str, Any]]:
        """Get available shows for a specific movie"""
        try:
            if date is None:
                date = datetime.now().date()
            
            shows = db.session.query(
                Show.id,
                Show.show_date,
                Show.show_time,
                Show.end_time,
                Show.base_price,
                Show.weekend_surcharge,
                Show.matinee_discount,
                Show.show_type,
                Screen.id.label('screen_id'),
                Screen.name.label('screen_name'),
                Movie.title.label('movie_title'),
                Movie.duration
            ).join(
                Screen, Show.screen_id == Screen.id
            ).join(
                Movie, Show.movie_id == Movie.id
            ).filter(
                Show.movie_id == movie_id,
                Show.show_date == date,
                Show.status == 'scheduled'
            ).all()
            
            result = []
            for show in shows:
                # Calculate availability
                total_seats = len(show.screen.seats) if hasattr(show, 'screen') and show.screen else 0
                available_seats = show.get_available_seats_count()
                
                result.append({
                    'id': show.id,
                    'show_date': show.show_date.isoformat(),
                    'show_time': show.show_time.strftime('%H:%M'),
                    'end_time': show.end_time.strftime('%H:%M'),
                    'base_price': float(show.base_price),
                    'weekend_surcharge': float(show.weekend_surcharge or 0),
                    'matinee_discount': float(show.matinee_discount or 0),
                    'show_type': show.show_type,
                    'screen_id': show.screen_id,
                    'screen_name': show.screen_name,
                    'movie_title': show.movie_title,
                    'movie_duration': show.duration,
                    'total_seats': total_seats,
                    'available_seats': available_seats,
                    'occupancy_percentage': show.get_occupancy_percentage()
                })
            
            return result
            
        except Exception as e:
            current_app.logger.error(f"Error getting movie shows: {str(e)}")
            return []
    
    @staticmethod
    def get_show_seat_layout(show_id: int) -> Dict[str, Any]:
        """Get seat layout for a specific show with availability status"""
        try:
            show = Show.query.get(show_id)
            if not show:
                return {'error': 'Show not found'}
            
            # Get all seats for the screen
            seats = db.session.query(Seat).filter_by(screen_id=show.screen_id).all()
            
            # Get occupied seats for this show
            occupied_seat_ids = db.session.query(BookingSeat.seat_id).join(Booking).filter(
                Booking.show_id == show_id,
                Booking.status.in_(['confirmed', 'pending'])
            ).all()
            occupied_seat_ids = [seat_id[0] for seat_id in occupied_seat_ids]
            
            # Get locked seats for this show
            locked_seats = SeatLock.get_locked_seats_for_show(show_id)
            locked_seat_ids = [lock.seat_id for lock in locked_seats]
            
            # Build seat layout
            seat_layout = {}
            seat_types = {'normal': [], 'premium': [], 'vip': []}
            
            for seat in seats:
                seat_info = {
                    'id': seat.id,
                    'row': seat.row,
                    'column': seat.column,
                    'seat_number': seat.seat_number,
                    'type': seat.type,
                    'base_price': float(seat.price),
                    'final_price': seat.get_price_for_show(show),
                    'status': 'available'
                }
                
                # Check if seat is occupied
                if seat.id in occupied_seat_ids:
                    seat_info['status'] = 'occupied'
                # Check if seat is locked
                elif seat.id in locked_seat_ids:
                    seat_info['status'] = 'locked'
                
                # Add to appropriate seat type category
                seat_types[seat.type].append(seat_info)
                
                # Add to seat layout grid
                if seat.row not in seat_layout:
                    seat_layout[seat.row] = {}
                seat_layout[seat.row][seat.column] = seat_info
            
            return {
                'show_id': show_id,
                'movie_title': show.movie.title,
                'screen_name': show.screen.name,
                'show_date': show.show_date.isoformat(),
                'show_time': show.show_time.strftime('%H:%M'),
                'seat_layout': seat_layout,
                'seat_types': seat_types,
                'total_seats': len(seats),
                'available_seats': len([s for s in seats if s.id not in occupied_seat_ids and s.id not in locked_seat_ids]),
                'occupied_seats': len(occupied_seat_ids),
                'locked_seats': len(locked_seat_ids)
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting show seat layout: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def reserve_seats(show_id: int, seat_ids: List[int], user_id: int, lock_minutes: int = 10) -> Dict[str, Any]:
        """Reserve seats for a show"""
        try:
            show = Show.query.get(show_id)
            if not show:
                return {'success': False, 'error': 'Show not found'}
            
            # Check if seats exist and are available
            seats = Seat.query.filter(Seat.id.in_(seat_ids)).all()
            if len(seats) != len(seat_ids):
                return {'success': False, 'error': 'One or more seats not found'}
            
            # Check seat availability
            for seat in seats:
                if seat.screen_id != show.screen_id:
                    return {'success': False, 'error': f'Seat {seat.seat_number} is not in this screen'}
                
                # Check if seat is already booked
                existing_booking = db.session.query(BookingSeat).join(Booking).filter(
                    BookingSeat.seat_id == seat.id,
                    Booking.show_id == show_id,
                    Booking.status.in_(['confirmed', 'pending'])
                ).first()
                
                if existing_booking:
                    return {'success': False, 'error': f'Seat {seat.seat_number} is already booked'}
                
                # Check if seat is locked
                if SeatLock.is_seat_locked(seat.id, show_id):
                    return {'success': False, 'error': f'Seat {seat.seat_number} is currently locked'}
            
            # Lock seats
            lock_results = []
            for seat_id in seat_ids:
                success, message = SeatLock.lock_seat(seat_id, show_id, user_id, lock_minutes)
                lock_results.append({'seat_id': seat_id, 'success': success, 'message': message})
            
            failed_locks = [r for r in lock_results if not r['success']]
            if failed_locks:
                # Release any successful locks
                for seat_id in seat_ids:
                    SeatLock.release_lock(seat_id, show_id, user_id)
                return {'success': False, 'error': 'Failed to lock some seats', 'details': failed_locks}
            
            return {
                'success': True,
                'message': f'Seats locked for {lock_minutes} minutes',
                'locked_seats': seat_ids,
                'expires_at': (datetime.utcnow() + timedelta(minutes=lock_minutes)).isoformat()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error reserving seats: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def create_booking(show_id: int, seat_ids: List[int], customer_info: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Create a booking with reserved seats"""
        try:
            show = Show.query.get(show_id)
            if not show:
                return {'success': False, 'error': 'Show not found'}
            
            # Verify seats are locked by this user
            for seat_id in seat_ids:
                if not SeatLock.is_seat_locked(seat_id, show_id):
                    return {'success': False, 'error': 'One or more seats are not locked'}
            
            # Get seats and calculate total amount
            seats = Seat.query.filter(Seat.id.in_(seat_ids)).all()
            total_amount = sum(seat.get_price_for_show(show) for seat in seats)
            
            # Create booking
            booking = Booking(
                show_id=show_id,
                user_id=user_id,
                total_amount=total_amount,
                customer_name=customer_info.get('customer_name', ''),
                customer_phone=customer_info.get('customer_phone', ''),
                customer_email=customer_info.get('customer_email', ''),
                payment_method=customer_info.get('payment_method', 'cash'),
                status='pending'
            )
            booking.generate_reference_number()
            
            db.session.add(booking)
            db.session.flush()  # Get booking ID
            
            # Create booking seats
            for seat in seats:
                booking_seat = BookingSeat(
                    booking_id=booking.id,
                    seat_id=seat.id,
                    price=seat.get_price_for_show(show),
                    status='booked'
                )
                db.session.add(booking_seat)
                
                # Release seat lock
                SeatLock.release_lock(seat.id, show_id, user_id)
            
            db.session.commit()
            
            return {
                'success': True,
                'booking_id': booking.id,
                'reference_number': booking.reference_number,
                'total_amount': float(total_amount),
                'seats': [seat.seat_number for seat in seats],
                'message': 'Booking created successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating booking: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def process_payment(booking_id: int, payment_info: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Process payment for a booking"""
        try:
            booking = Booking.query.get(booking_id)
            if not booking:
                return {'success': False, 'error': 'Booking not found'}
            
            if booking.status != 'pending':
                return {'success': False, 'error': 'Booking is not in pending status'}
            
            # Create payment record
            payment = Payment(
                booking_id=booking_id,
                amount=booking.total_amount,
                mode=payment_info.get('mode', 'cash'),
                reference_id=payment_info.get('reference_id'),
                created_by=user_id
            )
            
            # Add payment method specific fields
            if payment_info.get('mode') == 'card':
                payment.card_type = payment_info.get('card_type')
                payment.card_last_4 = payment_info.get('card_last_4')
                payment.card_expiry_month = payment_info.get('card_expiry_month')
                payment.card_expiry_year = payment_info.get('card_expiry_year')
            elif payment_info.get('mode') == 'upi':
                payment.upi_id = payment_info.get('upi_id')
                payment.utr_number = payment_info.get('utr_number')
            elif payment_info.get('mode') == 'paypal':
                payment.paypal_order_id = payment_info.get('paypal_order_id')
                payment.paypal_capture_id = payment_info.get('paypal_capture_id')
            
            db.session.add(payment)
            db.session.flush()
            
            # Process payment based on mode
            if payment_info.get('mode') == 'cash':
                payment.mark_completed()
                booking.confirm_booking()
            elif payment_info.get('mode') == 'paypal':
                if payment_info.get('paypal_status') == 'completed':
                    payment.mark_completed()
                    booking.confirm_booking()
                else:
                    payment.mark_processing()
            else:
                # For other payment modes, mark as processing
                payment.mark_processing()
            
            db.session.commit()
            
            return {
                'success': True,
                'payment_id': payment.id,
                'booking_id': booking_id,
                'reference_number': booking.reference_number,
                'amount': float(booking.total_amount),
                'status': payment.status,
                'message': 'Payment processed successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error processing payment: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def complete_booking_workflow(movie_id: int, show_id: int, seat_ids: List[int], 
                                 customer_info: Dict[str, Any], payment_info: Dict[str, Any], 
                                 user_id: int) -> Dict[str, Any]:
        """Complete the entire booking workflow in one transaction"""
        try:
            # Step 1: Reserve seats
            reservation_result = BookingWorkflow.reserve_seats(show_id, seat_ids, user_id)
            if not reservation_result['success']:
                return reservation_result
            
            # Step 2: Create booking
            booking_result = BookingWorkflow.create_booking(show_id, seat_ids, customer_info, user_id)
            if not booking_result['success']:
                # Release any seat locks
                for seat_id in seat_ids:
                    SeatLock.release_lock(seat_id, show_id, user_id)
                return booking_result
            
            # Step 3: Process payment
            payment_info['booking_id'] = booking_result['booking_id']
            payment_result = BookingWorkflow.process_payment(booking_result['booking_id'], payment_info, user_id)
            if not payment_result['success']:
                # Cancel the booking
                booking = Booking.query.get(booking_result['booking_id'])
                booking.cancel_booking()
                return payment_result
            
            return {
                'success': True,
                'booking_id': booking_result['booking_id'],
                'reference_number': booking_result['reference_number'],
                'payment_id': payment_result['payment_id'],
                'total_amount': booking_result['total_amount'],
                'seats': booking_result['seats'],
                'message': 'Booking completed successfully'
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in complete booking workflow: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def cancel_booking(booking_id: int, user_id: int, reason: str = None) -> Dict[str, Any]:
        """Cancel a booking and process refund if applicable"""
        try:
            booking = Booking.query.get(booking_id)
            if not booking:
                return {'success': False, 'error': 'Booking not found'}
            
            if booking.status == 'cancelled':
                return {'success': False, 'error': 'Booking is already cancelled'}
            
            # Check if payment was completed
            payment = Payment.query.filter_by(booking_id=booking_id, status='completed').first()
            
            # Cancel booking
            booking.cancel_booking()
            
            # Process refund if payment was completed
            if payment:
                payment.mark_refunded(
                    refund_amount=payment.amount,
                    refund_reason=reason or 'Customer cancellation',
                    refund_method=payment.mode
                )
            
            db.session.commit()
            
            return {
                'success': True,
                'booking_id': booking_id,
                'reference_number': booking.reference_number,
                'refund_amount': float(payment.amount) if payment else 0,
                'message': 'Booking cancelled successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error cancelling booking: {str(e)}")
            return {'success': False, 'error': str(e)}


class ReportingWorkflow:
    """Complete reporting workflow across all modules"""
    
    @staticmethod
    def generate_comprehensive_report(start_date: datetime.date, end_date: datetime.date, 
                                    report_type: str = 'daily') -> Dict[str, Any]:
        """Generate comprehensive reports across all modules"""
        try:
            if report_type == 'daily':
                return ReportingWorkflow._generate_daily_report(start_date, end_date)
            elif report_type == 'weekly':
                return ReportingWorkflow._generate_weekly_report(start_date, end_date)
            elif report_type == 'monthly':
                return ReportingWorkflow._generate_monthly_report(start_date, end_date)
            elif report_type == 'custom':
                return ReportingWorkflow._generate_custom_report(start_date, end_date)
            else:
                return {'error': 'Invalid report type'}
                
        except Exception as e:
            current_app.logger.error(f"Error generating comprehensive report: {str(e)}")
            return {'error': str(e)}
    
    @staticmethod
    def _generate_daily_report(start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """Generate daily report"""
        from app.reports.models import ReportQueries
        
        # Get daily sales data
        daily_sales = []
        current_date = start_date
        while current_date <= end_date:
            sales_data = ReportQueries.get_daily_sales_data(current_date)
            daily_sales.append({
                'date': current_date.isoformat(),
                'sales': [dict(row._mapping) for row in sales_data]
            })
            current_date += timedelta(days=1)
        
        # Get payment method breakdown
        payment_methods = ReportQueries.get_payment_method_breakdown(start_date, end_date)
        
        # Get occupancy data
        occupancy_data = ReportQueries.get_occupancy_data(start_date, end_date)
        
        # Get cashier performance
        cashier_performance = ReportQueries.get_cashier_performance_data(start_date, end_date)
        
        return {
            'report_type': 'daily',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'daily_sales': daily_sales,
            'payment_methods': [dict(row._mapping) for row in payment_methods],
            'occupancy_data': [dict(row._mapping) for row in occupancy_data],
            'cashier_performance': [dict(row._mapping) for row in cashier_performance]
        }
    
    @staticmethod
    def _generate_weekly_report(start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """Generate weekly report"""
        from app.reports.models import ReportQueries
        
        # Get movie performance
        movie_performance = ReportQueries.get_movie_performance_data(start_date, end_date)
        
        # Get screen utilization
        screen_utilization = ReportQueries.get_screen_utilization_data(start_date, end_date)
        
        # Get peak occupancy times
        peak_times = ReportQueries.get_peak_occupancy_times(start_date, end_date)
        
        return {
            'report_type': 'weekly',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'movie_performance': [dict(row._mapping) for row in movie_performance],
            'screen_utilization': [dict(row._mapping) for row in screen_utilization],
            'peak_times': peak_times
        }
    
    @staticmethod
    def _generate_monthly_report(start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """Generate monthly report"""
        from app.reports.models import ReportQueries
        
        # Get payment trends
        payment_trends = ReportQueries.get_payment_trends(start_date, end_date)
        
        # Get refund analysis
        refund_analysis = ReportQueries.get_refund_analysis(start_date, end_date)
        
        # Get customer behavior metrics
        customer_behavior = ReportQueries.get_customer_behavior_metrics(start_date, end_date)
        
        return {
            'report_type': 'monthly',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'payment_trends': [dict(row._mapping) for row in payment_trends],
            'refund_analysis': [dict(row._mapping) for row in refund_analysis],
            'customer_behavior': customer_behavior
        }
    
    @staticmethod
    def _generate_custom_report(start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """Generate custom report with all available data"""
        from app.reports.models import ReportQueries
        
        # Combine all report types
        daily_sales = ReportQueries.get_daily_sales_data(start_date, end_date)
        movie_performance = ReportQueries.get_movie_performance_data(start_date, end_date)
        screen_utilization = ReportQueries.get_screen_utilization_data(start_date, end_date)
        payment_methods = ReportQueries.get_payment_method_breakdown(start_date, end_date)
        cashier_performance = ReportQueries.get_cashier_performance_data(start_date, end_date)
        occupancy_data = ReportQueries.get_occupancy_data(start_date, end_date)
        
        return {
            'report_type': 'custom',
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'daily_sales': [dict(row._mapping) for row in daily_sales],
            'movie_performance': [dict(row._mapping) for row in movie_performance],
            'screen_utilization': [dict(row._mapping) for row in screen_utilization],
            'payment_methods': [dict(row._mapping) for row in payment_methods],
            'cashier_performance': [dict(row._mapping) for row in cashier_performance],
            'occupancy_data': [dict(row._mapping) for row in occupancy_data]
        }
    
    @staticmethod
    def export_report_to_csv(report_data: Dict[str, Any], filename: str = None) -> Dict[str, Any]:
        """Export report data to CSV format"""
        try:
            import csv
            import io
            from flask import make_response
            
            if filename is None:
                filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Report Type', report_data.get('report_type', 'Unknown')])
            writer.writerow(['Period', f"{report_data.get('period', {}).get('start_date', '')} to {report_data.get('period', {}).get('end_date', '')}"])
            writer.writerow([])  # Empty row
            
            # Write different sections based on report type
            if 'daily_sales' in report_data:
                writer.writerow(['Daily Sales'])
                writer.writerow(['Date', 'Movie', 'Screen', 'Bookings', 'Revenue', 'Tickets Sold'])
                for day_data in report_data['daily_sales']:
                    for sale in day_data.get('sales', []):
                        writer.writerow([
                            day_data.get('date', ''),
                            sale.get('movie_title', ''),
                            sale.get('screen_name', ''),
                            sale.get('bookings_count', 0),
                            sale.get('revenue', 0),
                            sale.get('tickets_sold', 0)
                        ])
                writer.writerow([])
            
            if 'movie_performance' in report_data:
                writer.writerow(['Movie Performance'])
                writer.writerow(['Movie', 'Bookings', 'Tickets Sold', 'Revenue'])
                for movie in report_data['movie_performance']:
                    writer.writerow([
                        movie.get('title', ''),
                        movie.get('bookings_count', 0),
                        movie.get('tickets_sold', 0),
                        movie.get('revenue', 0)
                    ])
                writer.writerow([])
            
            if 'screen_utilization' in report_data:
                writer.writerow(['Screen Utilization'])
                writer.writerow(['Screen', 'Shows', 'Bookings', 'Tickets Sold', 'Revenue', 'Utilization %'])
                for screen in report_data['screen_utilization']:
                    writer.writerow([
                        screen.get('name', ''),
                        screen.get('total_shows', 0),
                        screen.get('total_bookings', 0),
                        screen.get('total_tickets_sold', 0),
                        screen.get('total_revenue', 0),
                        screen.get('average_occupancy', 0)
                    ])
            
            # Create response
            output.seek(0)
            response = make_response(output.getvalue())
            response.headers['Content-Disposition'] = f'attachment; filename={filename}'
            response.headers['Content-type'] = 'text/csv'
            
            return {
                'success': True,
                'filename': filename,
                'response': response
            }
            
        except Exception as e:
            current_app.logger.error(f"Error exporting report to CSV: {str(e)}")
            return {'success': False, 'error': str(e)}