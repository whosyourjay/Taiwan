#import <AppKit/AppKit.h>
#import <Vision/Vision.h>

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 2) {
            fprintf(stderr, "usage: vision_ocr IMAGE\n");
            return 2;
        }
        NSString *path = [NSString stringWithUTF8String:argv[1]];
        NSImage *image = [[NSImage alloc] initWithContentsOfFile:path];
        NSRect rect = NSMakeRect(0, 0, image.size.width, image.size.height);
        CGImageRef cgImage = [image CGImageForProposedRect:&rect context:nil hints:nil];
        if (!cgImage) {
            fprintf(stderr, "cannot decode %s\n", argv[1]);
            return 1;
        }
        VNRecognizeTextRequest *request = [[VNRecognizeTextRequest alloc] init];
        request.recognitionLevel = VNRequestTextRecognitionLevelFast;
        request.recognitionLanguages = @[@"zh-Hant", @"en-US"];
        request.usesLanguageCorrection = NO;
        VNImageRequestHandler *handler = [[VNImageRequestHandler alloc]
            initWithCGImage:cgImage options:@{}];
        NSError *error = nil;
        if (![handler performRequests:@[request] error:&error]) {
            fprintf(stderr, "%s\n", error.localizedDescription.UTF8String);
            return 1;
        }
        for (VNRecognizedTextObservation *result in request.results) {
            VNRecognizedText *candidate = [[result topCandidates:1] firstObject];
            if (!candidate) continue;
            CGRect box = result.boundingBox;
            printf("%.8f\t%.8f\t%.8f\t%.8f\t%s\n", box.origin.x,
                   box.origin.y, box.size.width, box.size.height,
                   candidate.string.UTF8String);
        }
    }
    return 0;
}
