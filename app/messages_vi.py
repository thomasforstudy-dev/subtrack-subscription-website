"""Vietnamese for the messages the server shows (flash messages, form errors).

The code writes its messages in English. When a visitor reads the site in
Vietnamese, app/i18n.say() looks the message up here first. Messages with a
changing part (a number, an email) are matched by a pattern instead.
A message missing from this file is simply shown in English.
"""

import re

VI = {
    # accounts
    "Please fill in username, email and password.": "Vui lòng nhập tên đăng nhập, email và mật khẩu.",
    "The two passwords don't match. Please type them again.": "Hai mật khẩu chưa giống nhau. Vui lòng nhập lại.",
    "That username is taken. Please try another one.": "Tên đăng nhập này đã có người dùng. Hãy chọn tên khác.",
    "That email is already registered. Try logging in instead.": "Email này đã được đăng ký. Hãy thử đăng nhập.",
    "That username or email was just taken. Please try another one.": "Tên đăng nhập hoặc email vừa có người dùng. Hãy thử lại.",
    "Welcome! We've emailed you a 6-digit code: type it in the yellow box (or click the link in the email).":
        "Chào mừng bạn! AllOutFree đã gửi mã 6 số tới email của bạn: nhập mã vào ô màu vàng (hoặc bấm liên kết trong email).",
    "Welcome! We couldn't send the confirmation email right now. You can resend it later.":
        "Chào mừng bạn! Hiện chưa gửi được email xác nhận. Bạn có thể gửi lại sau.",
    "Wrong email/username or password.": "Sai email/tên đăng nhập hoặc mật khẩu.",
    "That link has expired or was already used. Log in and ask for a new one.":
        "Liên kết đã hết hạn hoặc đã được dùng. Hãy đăng nhập và gửi lại email mới.",
    "Thanks! Your email is confirmed.": "Cảm ơn bạn! Email đã được xác nhận.",
    "Your email is already confirmed.": "Email của bạn đã được xác nhận rồi.",
    "Too many wrong codes. Please send yourself a new one.": "Nhập sai mã quá nhiều lần. Hãy gửi lại email để lấy mã mới.",
    "That was the 5th wrong code, so we cancelled it. Please send yourself a new one.":
        "Đây là lần nhập sai thứ 5 nên mã đã bị hủy. Hãy gửi lại email để lấy mã mới.",
    "That code isn't right or has expired. Check the newest email from AllOutFree.":
        "Mã chưa đúng hoặc đã hết hạn. Hãy xem email mới nhất từ AllOutFree.",
    "We've sent a few emails already. Please check your spam folder, or try again in an hour.":
        "Đã gửi vài email rồi. Hãy xem thư mục Spam, hoặc thử lại sau một giờ.",
    "We couldn't send the email right now. Please try again later.": "Hiện chưa gửi được email. Vui lòng thử lại sau.",
    "Password reset emails aren't switched on yet. Please contact us for help.":
        "Chức năng gửi email đặt lại mật khẩu chưa bật. Vui lòng liên hệ để được giúp.",
    "Too many requests. Please try again in an hour.": "Quá nhiều yêu cầu. Vui lòng thử lại sau một giờ.",
    "That reset link has expired or was already used. Please ask for a new one.":
        "Liên kết đặt lại mật khẩu đã hết hạn hoặc đã được dùng. Hãy yêu cầu liên kết mới.",
    "Password changed. Please log in with your new password.": "Đã đổi mật khẩu. Hãy đăng nhập bằng mật khẩu mới.",
    "Your email is now confirmed. To log in with a password too, use \"Forgot password\".":
        "Email của bạn đã được xác nhận. Muốn đăng nhập bằng mật khẩu, hãy dùng \"Quên mật khẩu\".",
    "This page expired. Please go back, reload it and try again.": "Trang này đã hết hạn. Hãy quay lại, tải lại trang rồi thử lần nữa.",
    "Usernames are 3–30 characters: letters a–z, numbers and _ only.":
        "Tên đăng nhập gồm 3–30 ký tự: chỉ chữ a–z, số và dấu _.",
    "Please type a real email address, like name@example.com.": "Vui lòng nhập email thật, ví dụ ten@example.com.",
    # settings
    "Please pick a time zone from the list.": "Vui lòng chọn múi giờ trong danh sách.",
    "Pick an hour from 0 to 23.": "Chọn giờ từ 0 đến 23.",
    "Settings saved.": "Đã lưu cài đặt.",
    # subscriptions
    "Subscription saved.": "Đã lưu gói đăng ký.",
    "Subscription updated.": "Đã cập nhật gói đăng ký.",
    "Archived. Reminders for it have stopped.": "Đã lưu trữ. Gói này sẽ không được nhắc nữa.",
    "Restored.": "Đã khôi phục.",
    "Archived.": "Đã lưu trữ.",
    "Please give it a name (up to 120 characters).": "Vui lòng đặt tên cho gói (tối đa 120 ký tự).",
    "Please type the price as a number like 9.99 (dot for decimals, at most 2 decimals).":
        "Vui lòng nhập giá dạng số như 9.99 (dấu chấm cho phần thập phân, tối đa 2 chữ số).",
    "Use a 3-letter currency code, like USD, EUR or VND.": "Dùng mã tiền tệ 3 chữ cái, ví dụ USD, EUR hoặc VND.",
    "Pick weekly, monthly or yearly.": "Chọn hằng tuần, hằng tháng hoặc hằng năm.",
    "Please pick the next renewal date.": "Vui lòng chọn ngày gia hạn tiếp theo.",
    "That renewal date looks wrong. Please check the year.": "Ngày gia hạn có vẻ sai. Hãy kiểm tra lại năm.",
    "Notes can be up to 2000 characters.": "Ghi chú tối đa 2000 ký tự.",
    # links
    "Link saved.": "Đã lưu link.",
    "Link updated.": "Đã cập nhật link.",
    "Link deleted.": "Đã xóa link.",
    "Please paste a link.": "Vui lòng dán một đường link.",
    "That doesn't look like a web link (it should start with http:// or https://).":
        "Đây chưa phải link web (link phải bắt đầu bằng http:// hoặc https://).",
    "That link is too long (max 2048 characters).": "Link quá dài (tối đa 2048 ký tự).",
    "A web link can't contain spaces. Please check it.": "Link web không được có dấu cách. Hãy kiểm tra lại.",
    "That link has a mistake in it. Please check the address and port number.":
        "Link bị sai. Hãy kiểm tra lại địa chỉ và cổng (port).",
    # bills and uploads
    "Bill saved.": "Đã lưu hóa đơn.",
    "Bill updated.": "Đã cập nhật hóa đơn.",
    "Marked as paid.": "Đã đánh dấu là đã trả.",
    "Marked as not paid.": "Đã đánh dấu là chưa trả.",
    "Pick receipt or card bill.": "Chọn biên lai hoặc sao kê thẻ.",
    "Pick a category from the list.": "Chọn một danh mục trong danh sách.",
    "Time: please use hours and minutes, like 14:30.": "Giờ: dùng giờ và phút, ví dụ 14:30.",
    "Pick a time zone from the list, like Asia/Ho_Chi_Minh.": "Chọn múi giờ trong danh sách, ví dụ Asia/Ho_Chi_Minh.",
    "Card: type only the last 4 digits. Never the full card number.": "Thẻ: chỉ nhập 4 số cuối. Không bao giờ nhập cả số thẻ.",
    "Please pick the payment due date of the card bill.": "Vui lòng chọn hạn thanh toán của sao kê thẻ.",
    "The statement can't end before it starts.": "Kỳ sao kê không thể kết thúc trước khi bắt đầu.",
    "Please choose a file first.": "Vui lòng chọn tệp trước.",
    "You already uploaded this file.": "Bạn đã tải tệp này lên rồi.",
    "File saved. Now type in the bill details next to it.": "Đã lưu tệp. Giờ hãy nhập thông tin hóa đơn bên cạnh.",
    "That file is bigger than 10 MB. Please upload a smaller one.": "Tệp lớn hơn 10 MB. Vui lòng tải tệp nhỏ hơn.",
    "That file is empty.": "Tệp này trống.",
    "Please upload a PNG, JPG or WEBP photo, a PDF, or a Word (.docx) file.":
        "Vui lòng tải ảnh PNG, JPG hoặc WEBP, tệp PDF hoặc Word (.docx).",
    "Old .doc files aren't supported yet. Please save it as .docx or PDF and try again.":
        "Chưa hỗ trợ tệp .doc cũ. Hãy lưu thành .docx hoặc PDF rồi thử lại.",
    "This photo looks damaged. Please take or save it again.": "Ảnh có vẻ bị lỗi. Hãy chụp hoặc lưu lại ảnh.",
    "This photo is too large in pixels. Please upload a smaller copy.": "Ảnh quá lớn. Hãy tải bản nhỏ hơn.",
    "Animated pictures aren't supported. Please upload a normal photo.": "Chưa hỗ trợ ảnh động. Hãy tải ảnh thường.",
    "This PDF is password-protected. Please upload a copy without a password.": "PDF này có mật khẩu. Hãy tải bản không có mật khẩu.",
    "This PDF looks damaged. Please save or export it again and retry.": "PDF có vẻ bị lỗi. Hãy lưu hoặc xuất lại rồi thử lại.",
    "This PDF has no pages.": "PDF này không có trang nào.",
    "This Word file looks damaged. Please save it again and retry.": "Tệp Word có vẻ bị lỗi. Hãy lưu lại rồi thử lại.",
    "This Word file is password-protected. Please upload a copy without a password.":
        "Tệp Word có mật khẩu. Hãy tải bản không có mật khẩu.",
    "This Word file is too big once opened.": "Tệp Word quá lớn khi mở ra.",
    "This Word file is too complicated to read.": "Tệp Word quá phức tạp để đọc.",
    "This file took too long to check. Please upload a simpler copy.": "Kiểm tra tệp quá lâu. Hãy tải bản đơn giản hơn.",
    # reading bills
    "Queued: we'll read this file and prepare a draft for you to check.":
        "Đã xếp hàng: AllOutFree sẽ đọc tệp và chuẩn bị bản nháp để bạn kiểm tra.",
    "This file is already being read (or was read).": "Tệp này đang được đọc (hoặc đã đọc xong).",
    "Queued again.": "Đã xếp hàng lại.",
    "Only a job that failed can be tried again.": "Chỉ thử lại được việc đọc đã thất bại.",
    "This draft is closed: it was already accepted or put aside.": "Bản nháp đã đóng: đã được chấp nhận hoặc bỏ qua.",
    "This draft changed in another tab. Here is the newest version; please check it again.":
        "Bản nháp vừa đổi ở tab khác. Đây là bản mới nhất, hãy kiểm tra lại.",
    "This draft changed in another tab. Here is the newest version.": "Bản nháp vừa đổi ở tab khác. Đây là bản mới nhất.",
    "Nothing changed.": "Không có gì thay đổi.",
    "This draft was already accepted or changed in another tab.": "Bản nháp đã được chấp nhận hoặc đổi ở tab khác.",
    "Bill saved from your checked draft.": "Đã lưu hóa đơn từ bản nháp bạn đã kiểm tra.",
    "Draft put aside. You can type the bill in yourself.": "Đã bỏ qua bản nháp. Bạn có thể tự nhập hóa đơn.",
    "This draft is already closed.": "Bản nháp này đã đóng.",
    # extension tokens
    "Pick what the token may see.": "Chọn những gì mã được xem.",
    # settings: test email
    "Confirm your email first, then try the test email.": "Hãy xác nhận email trước, rồi thử gửi email.",
    "You've sent a few test emails already. Please try again in an hour.": "Bạn đã gửi vài email thử rồi. Hãy thử lại sau một giờ.",
    "Test email sent. Check your inbox (and the spam folder).": "Đã gửi email thử. Hãy xem hộp thư (và cả thư rác).",
    "We couldn't send the email right now. Please try again later.": "Chưa gửi được email lúc này. Vui lòng thử lại sau.",
    "Links to private or local addresses (like 127.0.0.1 or your router) can't be saved.":
        "Không lưu được link tới địa chỉ nội bộ (như 127.0.0.1 hoặc router của bạn).",
    # bill reading jobs
    "Photos and scanned pages need OCR, and OCR isn't switched on yet. Type the bill in, or try again later.": 'Ảnh và trang quét cần OCR, mà OCR chưa được bật. Hãy tự nhập hóa đơn, hoặc thử lại sau.',
    "The OCR computer didn't answer. We'll try again a few times; you can also type the bill in.": 'Máy OCR không trả lời. Chúng tôi sẽ thử lại vài lần; bạn cũng có thể tự nhập hóa đơn.',
    "The OCR computer is busy. We'll try again a few times.": 'Máy OCR đang bận. Chúng tôi sẽ thử lại vài lần.',
    "The OCR computer sent something we couldn't use. Type the bill in, or try again later.": 'Máy OCR gửi về dữ liệu không dùng được. Hãy tự nhập hóa đơn, hoặc thử lại sau.',
    'Reading this file took too long.': 'Đọc tệp này mất quá lâu.',
    'Reading this file failed unexpectedly.': 'Đọc tệp này bị lỗi bất ngờ.',
    "This file couldn't be read. Type the bill in instead.": 'Không đọc được tệp này. Hãy tự nhập hóa đơn.',
    'This Word file is too big to read.': 'Tệp Word này quá lớn để đọc.',
    "The reader's answer couldn't be trusted, so nothing was filled in. Type the bill in.": 'Kết quả đọc không đáng tin, nên không ô nào được điền. Hãy tự nhập hóa đơn.',
    'The uploaded file is missing on the server.': 'Không tìm thấy tệp đã tải lên trên máy chủ.',
    'Reading kept failing, so we stopped trying.': 'Đọc thất bại nhiều lần nên đã dừng thử.',
    # read aloud
    "That PDF is bigger than 40 MB.": "Tệp PDF lớn hơn 40 MB.",
    "Word files can be up to 10 MB. A PDF can be up to 40 MB.": "Tệp Word tối đa 10 MB. Tệp PDF tối đa 40 MB.",
    "Please upload a PDF or a Word (.docx) file.": "Vui lòng tải lên tệp PDF hoặc Word (.docx).",
    "That PDF took too long to read. Try a smaller part of it.": "Đọc tệp PDF quá lâu. Hãy thử một phần nhỏ hơn.",
    "We couldn't read that file. A PDF must not be locked and can have up to 300 pages.":
        "Không đọc được tệp này. PDF không được khóa mật khẩu và tối đa 300 trang.",
    "There is no text to read. A scanned PDF needs OCR, which isn't switched on yet.":
        "Không có chữ để đọc. PDF dạng ảnh quét cần OCR, tính năng này chưa bật.",
    "Upload a file or paste some text first.": "Hãy tải tệp lên hoặc dán đoạn chữ trước.",
    # card holder
    "Type the first 6 and the last 4 digits of the card, numbers only.": "Nhập 6 số đầu và 4 số cuối của thẻ, chỉ gồm chữ số.",
    "The card holder fits 12 cards. Remove one first.": "Ví thẻ chứa tối đa 12 thẻ. Hãy bỏ bớt một thẻ trước.",
    "Card added to your card holder.": "Đã thêm thẻ vào ví thẻ.",
    "Card removed from your card holder.": "Đã bỏ thẻ khỏi ví thẻ.",
}

# Messages with a changing part. {0}, {1} ... are the parts in brackets.
PATTERNS = [
    (r"Too many tries\. Please wait (\d+) minutes, or reset your password\.",
     "Thử quá nhiều lần. Vui lòng chờ {0} phút, hoặc đặt lại mật khẩu."),
    (r"Sent! Check (.+) for the new code \(older codes stop working\)\.",
     "Đã gửi! Hãy xem {0} để lấy mã mới (mã cũ không dùng được nữa)."),
    (r"If that email has an account, we've sent it a link to reset the password\. The link works for (\d+) minutes\.",
     "Nếu email này có tài khoản, AllOutFree đã gửi liên kết đặt lại mật khẩu. Liên kết dùng được trong {0} phút."),
    (r"Your password needs (\d+) to (\d+) characters\.", "Mật khẩu cần từ {0} đến {1} ký tự."),
    (r"Your password also needs (.+)\.", "Mật khẩu cần thêm {0}."),
    (r"Please check: (.+)", "Vui lòng kiểm tra: {0}"),
    (r"Remind me: up to (\d+) numbers of days from 0 to 365, like 14, 7, 3\.",
     "Nhắc trước: tối đa {0} mốc ngày từ 0 đến 365, ví dụ 14, 7, 3."),
    (r"Manage link: (.+)", "Link quản lý: {0}"),
    (r"You already saved this link as “(.+)”\. Search for it, or edit that one\.",
     "Bạn đã lưu link này với tên “{0}”. Hãy tìm hoặc sửa link đó."),
    (r"This PDF has (\d+) pages\. Please upload at most (\d+) pages\.", "PDF này có {0} trang. Vui lòng tải tối đa {1} trang."),
    (r"Please type the (shop|card or bank) name\.", "Vui lòng nhập tên {0}."),
    (r"The items add up to (\S+), but the (subtotal|total) says (\S+)\.", "Các món cộng lại {0}, nhưng {1} ghi {2}."),
    (r"Subtotal (\S+) \+ tax (\S+) = (\S+), but the total says (\S+)\.", "Tạm tính {0} + thuế {1} = {2}, nhưng tổng ghi {3}."),
    (r"Give the token a name of up to (\d+) characters, like “Chrome on my laptop”\.",
     "Đặt tên cho mã, tối đa {0} ký tự, ví dụ “Chrome trên laptop”."),
    (r"Pick how long it works: 1 to (\d+) days\.", "Chọn thời hạn: từ 1 đến {0} ngày."),
    (r"You already have (\d+) active tokens\. Revoke one first\.", "Bạn đã có {0} mã đang dùng. Hãy thu hồi một mã trước."),
    (r"“(.+)” is revoked\. The extension using it has to connect again\.", "Đã thu hồi “{0}”. Tiện ích dùng mã này phải kết nối lại."),
    (r"(.+) sign-in was cancelled or expired\. Please try again\.", "Đăng nhập bằng {0} đã bị hủy hoặc hết hạn. Vui lòng thử lại."),
    (r"We couldn't get a verified email from (.+)\. Please try another way\.",
     "Không lấy được email đã xác minh từ {0}. Hãy thử cách khác."),
    (r"Draft saved: (.+)\.", "Đã lưu bản nháp: {0}."),
]

# Small pieces inside the patterns above.
PARTS = {
    "an upper-case letter": "một chữ in hoa",
    "a number": "một chữ số",
    "a special character like ! or #": "một ký tự đặc biệt như ! hoặc #",
    "shop": "cửa hàng",
    "card or bank": "thẻ hoặc ngân hàng",
    "subtotal": "tạm tính",
    "total": "tổng",
}

COMPILED = [(re.compile(pattern), vi) for pattern, vi in PATTERNS]


def to_vietnamese(message: str) -> str:
    """The Vietnamese for an English message, or the message itself if unknown."""
    if message in VI:
        return VI[message]
    for pattern, vi in COMPILED:
        found = pattern.fullmatch(message)
        if found:
            parts = []
            for part in found.groups():
                if part in PARTS:
                    parts.append(PARTS[part])
                elif " and " in part:  # "an upper-case letter and a number"
                    parts.append(" và ".join(PARTS.get(p, p) for p in part.split(" and ")))
                else:
                    parts.append(to_vietnamese(part))
            return vi.format(*parts)
    return message
