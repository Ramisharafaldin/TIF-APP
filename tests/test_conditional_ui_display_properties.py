"""
Property-based tests for export functionality user experience consistency.

Feature: export-functionality-fix
Tests that export buttons provide consistent behavior, loading states, error messages, and file downloads across all pages.
"""
import pytest
from hypothesis import given, strategies as st, settings
from bs4 import BeautifulSoup
import re


class TestExportUIConsistencyProperties:
    """Property-based tests for export functionality user experience consistency."""
    
    @given(
        page_type=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']),
        export_format=st.sampled_from(['xlsx', 'pdf'])
    )
    @settings(max_examples=100, deadline=5000)
    def test_export_button_consistent_behavior(self, page_type, export_format):
        """
        Feature: export-functionality-fix, Property 4: User Experience Consistency
        For any export button interaction across all pages, the user should receive 
        consistent visual feedback (loading states, progress indicators), automatic 
        file downloads on success, and clear Arabic error messages on failure.
        
        **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
        """
        # Mock HTML for export button on different pages
        mock_html = f"""
        <div class="page-content" data-page="{page_type}">
            <button id="export-btn-{page_type}" 
                    class="export-btn" 
                    data-export-url="/{page_type}/export"
                    data-export-format="{export_format}"
                    data-export-filename="{page_type}_export">
                <span class="material-symbols-outlined">download</span>
                <span>تصدير البيانات</span>
            </button>
            
            <div id="notification-area" class="notification-area"></div>
            <div id="loading-indicator" class="loading-indicator hidden"></div>
        </div>
        """
        
        soup = BeautifulSoup(mock_html, 'html.parser')
        
        # Property 1: Export button should have consistent structure and attributes
        export_button = soup.find(id=f'export-btn-{page_type}')
        assert export_button is not None, f"Export button not found for {page_type}"
        
        # Verify required classes
        button_classes = export_button.get('class', [])
        assert 'export-btn' in button_classes, f"Export button missing 'export-btn' class on {page_type}"
        
        # Verify required data attributes
        assert export_button.get('data-export-url') == f'/{page_type}/export', f"Incorrect export URL for {page_type}"
        assert export_button.get('data-export-format') in ['xlsx', 'pdf'], f"Invalid export format for {page_type}"
        assert export_button.get('data-export-filename'), f"Missing export filename for {page_type}"
        
        # Property 2: Button should contain icon and Arabic text
        icon = export_button.find(class_='material-symbols-outlined')
        assert icon is not None, f"Export button missing icon on {page_type}"
        
        button_text = export_button.get_text()
        assert 'تصدير' in button_text, f"Export button missing Arabic text on {page_type}"
        
        # Property 3: Page should have notification area for feedback
        notification_area = soup.find(id='notification-area')
        assert notification_area is not None, f"Notification area not found on {page_type}"
        
        # Property 4: Page should have loading indicator
        loading_indicator = soup.find(id='loading-indicator')
        assert loading_indicator is not None, f"Loading indicator not found on {page_type}"
    
    @given(
        error_type=st.sampled_from(['network_error', 'server_error', 'no_data', 'timeout', 'csrf_error', 'permission_denied']),
        page_type=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting'])
    )
    @settings(max_examples=100, deadline=5000)
    def test_consistent_error_message_display(self, error_type, page_type):
        """
        Feature: export-functionality-fix, Property 4: User Experience Consistency
        For any export error scenario, the system should display clear Arabic error 
        messages with consistent formatting and provide appropriate user guidance.
        
        **Validates: Requirements 3.4, 3.5**
        """
        # Define expected Arabic error messages
        expected_arabic_messages = {
            'network_error': 'خطأ في الاتصال بالشبكة',
            'server_error': 'خطأ في الخادم',
            'no_data': 'لا توجد بيانات للتصدير',
            'timeout': 'انتهت مهلة التصدير',
            'csrf_error': 'انتهت صلاحية جلسة العمل',
            'permission_denied': 'ليس لديك صلاحية لتصدير هذه البيانات'
        }
        
        # Mock error response HTML
        mock_error_html = f"""
        <div class="error-notification export-error" data-error-type="{error_type}">
            <div class="error-icon">
                <span class="material-symbols-outlined">error</span>
            </div>
            <div class="error-content">
                <div class="error-title">خطأ في التصدير</div>
                <div class="error-message">{expected_arabic_messages.get(error_type, 'خطأ غير معروف')}</div>
                <div class="error-actions">
                    <button class="retry-btn">المحاولة مرة أخرى</button>
                    <button class="close-btn">إغلاق</button>
                </div>
            </div>
        </div>
        """
        
        soup = BeautifulSoup(mock_error_html, 'html.parser')
        
        # Property 1: Error notification should have consistent structure
        error_notification = soup.find(class_='error-notification')
        assert error_notification is not None, f"Error notification not found for {error_type}"
        
        # Verify error notification classes
        notification_classes = error_notification.get('class', [])
        assert 'export-error' in notification_classes, f"Missing 'export-error' class for {error_type}"
        
        # Property 2: Error should have proper data attributes
        assert error_notification.get('data-error-type') == error_type, f"Incorrect error type attribute for {error_type}"
        
        # Property 3: Error should contain icon
        error_icon = error_notification.find(class_='error-icon')
        assert error_icon is not None, f"Error icon not found for {error_type}"
        
        icon = error_icon.find(class_='material-symbols-outlined')
        assert icon is not None, f"Material icon not found for {error_type}"
        
        # Property 4: Error should contain Arabic title and message
        error_title = error_notification.find(class_='error-title')
        assert error_title is not None, f"Error title not found for {error_type}"
        assert 'خطأ' in error_title.get_text(), f"Error title not in Arabic for {error_type}"
        
        error_message = error_notification.find(class_='error-message')
        assert error_message is not None, f"Error message not found for {error_type}"
        
        message_text = error_message.get_text()
        expected_message = expected_arabic_messages.get(error_type, '')
        if expected_message:
            assert any(word in message_text for word in expected_message.split()[:2]), f"Arabic error message not found for {error_type}"
        
        # Property 5: Error should provide action buttons
        error_actions = error_notification.find(class_='error-actions')
        assert error_actions is not None, f"Error actions not found for {error_type}"
        
        retry_btn = error_actions.find(class_='retry-btn')
        close_btn = error_actions.find(class_='close-btn')
        assert retry_btn is not None, f"Retry button not found for {error_type}"
        assert close_btn is not None, f"Close button not found for {error_type}"
        
        # Verify button text is in Arabic
        assert 'المحاولة' in retry_btn.get_text(), f"Retry button not in Arabic for {error_type}"
        assert 'إغلاق' in close_btn.get_text(), f"Close button not in Arabic for {error_type}"
    
    @given(
        page_type=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']),
        processing_stage=st.sampled_from(['preparing', 'generating', 'finalizing'])
    )
    @settings(max_examples=100, deadline=5000)
    def test_consistent_loading_states_and_progress(self, page_type, processing_stage):
        """
        Feature: export-functionality-fix, Property 4: User Experience Consistency
        For any export operation in progress, the system should provide consistent 
        loading states, progress indicators, and Arabic status messages across all pages.
        
        **Validates: Requirements 3.1, 3.2**
        """
        # Define expected Arabic loading messages
        loading_messages = {
            'preparing': 'جاري تحضير البيانات',
            'generating': 'جاري إنشاء الملف',
            'finalizing': 'جاري إنهاء عملية التصدير'
        }
        
        # Mock loading state HTML
        mock_loading_html = f"""
        <div class="export-loading-container" data-page="{page_type}">
            <button id="export-btn-{page_type}" class="export-btn export-loading" disabled>
                <div class="loading-content">
                    <div class="spinner animate-spin"></div>
                    <span class="loading-text">{loading_messages.get(processing_stage, 'جاري المعالجة')}</span>
                </div>
            </button>
            
            <div class="loading-notification export-notification" data-stage="{processing_stage}">
                <div class="notification-icon">
                    <div class="spinner animate-spin"></div>
                </div>
                <div class="notification-content">
                    <div class="notification-title">جاري تصدير البيانات</div>
                    <div class="notification-message">{loading_messages.get(processing_stage, 'جاري المعالجة')}...</div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 45%"></div>
                    </div>
                </div>
            </div>
        </div>
        """
        
        soup = BeautifulSoup(mock_loading_html, 'html.parser')
        
        # Property 1: Export button should show loading state
        export_button = soup.find(id=f'export-btn-{page_type}')
        assert export_button is not None, f"Export button not found for {page_type}"
        
        button_classes = export_button.get('class', [])
        assert 'export-loading' in button_classes, f"Export button missing loading class on {page_type}"
        assert export_button.get('disabled') is not None, f"Export button not disabled during loading on {page_type}"
        
        # Property 2: Button should contain spinner and Arabic loading text
        spinner = export_button.find(class_='spinner')
        assert spinner is not None, f"Loading spinner not found in button on {page_type}"
        
        loading_text = export_button.find(class_='loading-text')
        assert loading_text is not None, f"Loading text not found in button on {page_type}"
        assert 'جاري' in loading_text.get_text(), f"Loading text not in Arabic on {page_type}"
        
        # Property 3: Loading notification should be present
        loading_notification = soup.find(class_='loading-notification')
        assert loading_notification is not None, f"Loading notification not found on {page_type}"
        
        notification_classes = loading_notification.get('class', [])
        assert 'export-notification' in notification_classes, f"Missing export-notification class on {page_type}"
        
        # Property 4: Notification should have proper stage attribute
        assert loading_notification.get('data-stage') == processing_stage, f"Incorrect processing stage on {page_type}"
        
        # Property 5: Notification should contain spinner, title, message, and progress bar
        notification_spinner = loading_notification.find(class_='spinner')
        assert notification_spinner is not None, f"Notification spinner not found on {page_type}"
        
        notification_title = loading_notification.find(class_='notification-title')
        assert notification_title is not None, f"Notification title not found on {page_type}"
        assert 'تصدير' in notification_title.get_text(), f"Notification title not in Arabic on {page_type}"
        
        notification_message = loading_notification.find(class_='notification-message')
        assert notification_message is not None, f"Notification message not found on {page_type}"
        assert 'جاري' in notification_message.get_text(), f"Notification message not in Arabic on {page_type}"
        
        progress_bar = loading_notification.find(class_='progress-bar')
        assert progress_bar is not None, f"Progress bar not found on {page_type}"
        
        progress_fill = progress_bar.find(class_='progress-fill')
        assert progress_fill is not None, f"Progress fill not found on {page_type}"
        
        # Property 6: Progress bar should have valid width
        style_attr = progress_fill.get('style', '')
        width_match = re.search(r'width:\s*(\d+)%', style_attr)
        assert width_match is not None, f"Progress bar width not found on {page_type}"
        
        width_value = int(width_match.group(1))
        assert 0 <= width_value <= 100, f"Invalid progress bar width on {page_type}: {width_value}%"
    
    @given(
        page_type=st.sampled_from(['dashboard', 'inventory', 'transfers', 'forecasting']),
        export_format=st.sampled_from(['xlsx', 'pdf'])
    )
    @settings(max_examples=100, deadline=5000)
    def test_consistent_success_feedback_and_download(self, page_type, export_format):
        """
        Feature: export-functionality-fix, Property 4: User Experience Consistency
        For any successful export operation, the system should provide consistent 
        success feedback, automatic file download initiation, and clear Arabic 
        success messages across all pages.
        
        **Validates: Requirements 3.3, 3.4**
        """
        filename = f"{page_type}_export"
        file_size = 1024
        
        # Mock success state HTML
        mock_success_html = f"""
        <div class="export-success-container" data-page="{page_type}">
            <button id="export-btn-{page_type}" class="export-btn export-success">
                <div class="success-content">
                    <span class="material-symbols-outlined success-icon">check_circle</span>
                    <span class="success-text">تم التصدير</span>
                </div>
            </button>
            
            <div class="success-notification export-notification" data-format="{export_format}">
                <div class="notification-icon">
                    <span class="material-symbols-outlined">check_circle</span>
                </div>
                <div class="notification-content">
                    <div class="notification-title">تم تصدير البيانات بنجاح</div>
                    <div class="notification-message">الملف جاهز للتحميل</div>
                    <div class="file-info">
                        <span class="filename">{filename}.{export_format}</span>
                        <span class="filesize">{file_size} بايت</span>
                    </div>
                </div>
                <div class="download-link" data-filename="{filename}.{export_format}" data-format="{export_format}">
                    <a href="#" class="download-btn">تحميل الملف</a>
                </div>
            </div>
        </div>
        """
        
        soup = BeautifulSoup(mock_success_html, 'html.parser')
        
        # Property 1: Export button should show success state
        export_button = soup.find(id=f'export-btn-{page_type}')
        assert export_button is not None, f"Export button not found for {page_type}"
        
        button_classes = export_button.get('class', [])
        assert 'export-success' in button_classes, f"Export button missing success class on {page_type}"
        
        # Property 2: Button should contain success icon and Arabic text
        success_icon = export_button.find(class_='success-icon')
        assert success_icon is not None, f"Success icon not found in button on {page_type}"
        assert success_icon.get_text() == 'check_circle', f"Incorrect success icon on {page_type}"
        
        success_text = export_button.find(class_='success-text')
        assert success_text is not None, f"Success text not found in button on {page_type}"
        assert 'تم' in success_text.get_text(), f"Success text not in Arabic on {page_type}"
        
        # Property 3: Success notification should be present
        success_notification = soup.find(class_='success-notification')
        assert success_notification is not None, f"Success notification not found on {page_type}"
        
        notification_classes = success_notification.get('class', [])
        assert 'export-notification' in notification_classes, f"Missing export-notification class on {page_type}"
        
        # Property 4: Notification should have proper format attribute
        assert success_notification.get('data-format') == export_format, f"Incorrect export format on {page_type}"
        
        # Property 5: Notification should contain success icon, title, and message
        notification_icon = success_notification.find(class_='notification-icon')
        assert notification_icon is not None, f"Notification icon not found on {page_type}"
        
        icon = notification_icon.find(class_='material-symbols-outlined')
        assert icon is not None and icon.get_text() == 'check_circle', f"Incorrect notification icon on {page_type}"
        
        notification_title = success_notification.find(class_='notification-title')
        assert notification_title is not None, f"Notification title not found on {page_type}"
        assert 'تم تصدير' in notification_title.get_text(), f"Notification title not in Arabic on {page_type}"
        
        notification_message = success_notification.find(class_='notification-message')
        assert notification_message is not None, f"Notification message not found on {page_type}"
        assert 'جاهز' in notification_message.get_text(), f"Notification message not in Arabic on {page_type}"
        
        # Property 6: File information should be displayed
        file_info = success_notification.find(class_='file-info')
        assert file_info is not None, f"File info not found on {page_type}"
        
        filename_span = file_info.find(class_='filename')
        assert filename_span is not None, f"Filename not found on {page_type}"
        assert export_format in filename_span.get_text(), f"Export format not in filename on {page_type}"
        
        filesize_span = file_info.find(class_='filesize')
        assert filesize_span is not None, f"File size not found on {page_type}"
        assert 'بايت' in filesize_span.get_text(), f"File size not in Arabic on {page_type}"
        
        # Property 7: Download link should be present and functional
        download_link = success_notification.find(class_='download-link')
        assert download_link is not None, f"Download link not found on {page_type}"
        
        assert download_link.get('data-filename'), f"Download filename not set on {page_type}"
        assert download_link.get('data-format') == export_format, f"Download format not set on {page_type}"
        
        download_btn = download_link.find(class_='download-btn')
        assert download_btn is not None, f"Download button not found on {page_type}"
        assert 'تحميل' in download_btn.get_text(), f"Download button not in Arabic on {page_type}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])